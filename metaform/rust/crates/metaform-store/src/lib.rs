//! Metaform's store: the data behind the one Metaform tool.
//!
//! - **Grouping** (R-4.1, `docs/designs/storage.md` 2.2). A map is the logical unit, with its
//!   own id, its own queue and its own snapshot. A database groups maps: a project's maps are
//!   partitions of `projects/<id>/project.lbug`; maps of no project share `maps/maps.lbug`.
//! - **One owner** (R-4.4, 2.5). `Store::open` takes `<home>/server.lock`. A second store on
//!   the same home is refused. Nothing else opens the databases.
//! - **Writes** (R-4.7). One writer thread per database, clients served in turn, one
//!   transaction per command, acknowledged after commit. A Ladybug commit is the commit point;
//!   there is no separate log (2.3).
//! - **Reads** run against the last committed snapshot of the map and never wait for writes.
//! - **Announcements** (R-4.10). Each commit is sent to the map's subscribers. Nothing polls.
//!
//! The command language is the one tool's, checked and applied by `metaform-core`.

mod graph;
mod registry;
pub use registry::Registered;
pub mod settings;
mod writer;

use std::collections::{HashMap, HashSet};
use std::fs::File;
use std::path::{Path, PathBuf};
use std::sync::mpsc;
use std::sync::{Arc, Mutex, RwLock};

pub use metaform_core::{Code, Refusal};
use metaform_core::{Contract, Effect, Map, Outcome, specification};
use serde_json::{Value, json};

use writer::{Job, Writer};

/// Who sent a command. The write manager serves clients in turn.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct ClientId(pub u64);

/// The database a map lives in.
#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub enum DbKey {
    /// A registered project's database, by its folder id under `projects/`.
    Project(String),
    /// The home's database for maps that belong to no project.
    Standalone,
}

/// The id of a project's main map within the project's database.
const MAIN_MAP: &str = "main";

/// A map: its database and its id within that database.
#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct MapKey {
    pub db: DbKey,
    pub map: String,
}

impl MapKey {
    /// A project's main map.
    pub fn main(project: &str) -> MapKey {
        MapKey {
            db: DbKey::Project(project.to_string()),
            map: MAIN_MAP.to_string(),
        }
    }

    /// Whether this is a project's main map.
    pub fn is_main(&self) -> bool {
        matches!(self.db, DbKey::Project(_)) && self.map == MAIN_MAP
    }

    /// A map that belongs to no project.
    pub fn standalone(map: &str) -> MapKey {
        MapKey {
            db: DbKey::Standalone,
            map: map.to_string(),
        }
    }
}

/// One committed change, as announced to subscribers.
#[derive(Clone, Debug, PartialEq)]
pub struct Announcement {
    pub map: MapKey,
    /// The final value of every element the write touched, in the agent's form; null if removed.
    pub changed: Value,
}

/// A store failure that is not a refusal of the command.
#[derive(Debug, thiserror::Error)]
pub enum StoreError {
    #[error("the home is owned by another functional map server (lock file {0})")]
    Owned(String),
    #[error("i/o error: {0}")]
    Io(#[from] std::io::Error),
    #[error("ladybug error: {0}")]
    Ladybug(String),
    #[error("stored data is not in the expected form: {0}")]
    Corrupt(String),
    #[error("the server could not write its layer definition: {0}")]
    Definition(String),
    #[error(
        "the database was made by a different build and cannot be brought up to date: {0}. \
         Nothing was changed. Use the build that made it, or another home"
    )]
    Schema(String),
    #[error("the writer has ended")]
    WriterGone,
    #[error("unknown project {0}")]
    UnknownProject(String),
    #[error("the bundled contract did not load: {0}")]
    Contract(String),
    #[error(
        "{0} holds data this store did not write (no {FORMAT_FILE}); it may be the Node test \
         harness's home. Nothing was changed. Use another home (METAFORM_HOME or --home)."
    )]
    ForeignHome(String),
}

impl From<lbug::Error> for StoreError {
    fn from(e: lbug::Error) -> Self {
        StoreError::Ladybug(e.to_string())
    }
}

/// Why `Store::execute_all` wrote nothing.
#[derive(Debug, thiserror::Error)]
#[error("{}{failure}", index.map(|i| format!("command {}: ", i + 1)).unwrap_or_default())]
pub struct BatchFailure {
    /// The position, from 0, of the command that was refused; `None` when the store failed.
    pub index: Option<usize>,
    pub failure: Failure,
}

/// Why a command did not succeed.
#[derive(Debug, thiserror::Error)]
pub enum Failure {
    /// The command broke a rule. The map is unchanged. Send `refusal.to_json()` to the agent.
    #[error("refused: {0:?}")]
    Refused(Refusal),
    #[error(transparent)]
    Store(#[from] StoreError),
}

/// Marks a home this store created. A home with data and no marker is refused, so the store
/// never writes into a home that another build, such as the Node test harness, owns.
pub const FORMAT_FILE: &str = "store.format";
const FORMAT: &str = "metaform-store 1\n";

type Snapshots = Arc<RwLock<HashMap<String, Arc<Map>>>>;
/// Called on the writer thread after each commit to its map. It must not block. Returning
/// false removes it.
pub type Sink = Box<dyn Fn(&Announcement) -> bool + Send>;

#[derive(Default)]
struct SubscriberList {
    next: u64,
    entries: Vec<(u64, MapKey, Sink)>,
}

type Subscribers = Arc<Mutex<SubscriberList>>;

/// A subscription made with `Store::watch`. Dropping it removes the subscriber at once, so a
/// subscription on a map nobody writes to leaves nothing behind.
pub struct Watch {
    id: u64,
    subscribers: std::sync::Weak<Mutex<SubscriberList>>,
}

impl Drop for Watch {
    fn drop(&mut self) {
        if let Some(list) = self.subscribers.upgrade() {
            list.lock().expect("subscriber lock").entries.retain(|(id, _, _)| *id != self.id);
        }
    }
}

/// One open grouping database. Field order is drop order: the writer ends before the
/// database closes.
struct DbHandle {
    writer: Writer,
    snapshots: Snapshots,
    db: Arc<lbug::Database>,
}

impl DbHandle {
    fn open(path: &Path, name: String) -> Result<DbHandle, StoreError> {
        if let Some(dir) = path.parent() {
            std::fs::create_dir_all(dir)?;
        }
        let db = Arc::new(graph::open(path)?);
        let writer = Writer::start(Arc::clone(&db), name)?;
        Ok(DbHandle {
            writer,
            snapshots: Arc::default(),
            db,
        })
    }

    /// The map's last committed state, loading it on first use.
    fn snapshot(&self, map: &str) -> Result<Arc<Map>, StoreError> {
        if let Some(found) = self.snapshots.read().expect("snapshot lock").get(map) {
            return Ok(Arc::clone(found));
        }
        let conn = lbug::Connection::new(&self.db)?;
        load_into(&self.snapshots, &conn, map)
    }
}

fn load_into(
    snapshots: &Snapshots,
    conn: &lbug::Connection,
    map: &str,
) -> Result<Arc<Map>, StoreError> {
    let mut all = snapshots.write().expect("snapshot lock");
    if let Some(found) = all.get(map) {
        return Ok(Arc::clone(found));
    }
    let loaded = Arc::new(graph::load(conn, map)?);
    all.insert(map.to_string(), Arc::clone(&loaded));
    Ok(loaded)
}

/// Databases a store keeps open at once by default (`docs/designs/storage.md` 2.4). Each
/// open Ladybug database reserves address space (default settings failed at about 7) and holds
/// about 28 MB of memory even when nearly empty: 64 open took 1.85 GB (storage note risk 5). 16
/// bounds that near 0.5 GB; the 17th project costs a cold load of a few milliseconds. The default
/// of the setting `stores.max_open_databases` (R-4.8).
pub const DEFAULT_MAX_OPEN: usize = 16;

/// Open grouping databases, with the tick of each one's last use.
#[derive(Default)]
struct OpenDbs {
    handles: HashMap<DbKey, (Arc<DbHandle>, u64)>,
    tick: u64,
}

/// The functional map server's store for one home. Field order is drop order: databases
/// close before the owner lock is released.
pub struct Store {
    dbs: Mutex<OpenDbs>,
    max_open: usize,
    chassis: DbHandle,
    subscribers: Subscribers,
    contract: Arc<Contract>,
    settings: settings::Settings,
    /// Main maps whose server-defined layers are current in this run (`ensure_defined`).
    defined: Mutex<HashSet<MapKey>>,
    home: PathBuf,
    _owner: File,
}

impl Store {
    /// Open the store for `home`, taking ownership. Fails with `StoreError::Owned` if another
    /// functional map server owns the home.
    /// The open-database cap is the setting `stores.max_open_databases` (R-4.8).
    pub fn open(home: &Path) -> Result<Store, StoreError> {
        let settings = settings::Settings::load(home);
        let max_open = settings
            .get("stores.max_open_databases", None)
            .and_then(|(v, _)| v.as_u64())
            .map_or(DEFAULT_MAX_OPEN, |n| n as usize);
        Store::open_with(home, max_open, settings)
    }

    /// As `open`, keeping at most `max_open` grouping databases open (at least 1), whatever the
    /// settings say. The least recently used database that no command is using closes first; its
    /// maps reload on next use.
    pub fn open_with_limit(home: &Path, max_open: usize) -> Result<Store, StoreError> {
        Store::open_with(home, max_open, settings::Settings::load(home))
    }

    /// The home's settings (R-4.8). The server is the only writer of them.
    pub fn settings(&self) -> &settings::Settings {
        &self.settings
    }

    fn open_with(home: &Path, max_open: usize, settings: settings::Settings) -> Result<Store, StoreError> {
        std::fs::create_dir_all(home)?;
        let lock_path = home.join("server.lock");
        let owner = File::options()
            .create(true)
            .truncate(false)
            .write(true)
            .open(&lock_path)?;
        if owner.try_lock().is_err() {
            return Err(StoreError::Owned(lock_path.display().to_string()));
        }
        let marker = home.join(FORMAT_FILE);
        if !marker.exists() {
            let has_data = std::fs::read_dir(home)?.filter_map(Result::ok).any(|e| {
                !matches!(
                    e.file_name().to_str(),
                    Some("server.lock" | "server.log" | "server.sock" | settings::SETTINGS_FILE)
                )
            });
            if has_data {
                return Err(StoreError::ForeignHome(home.display().to_string()));
            }
            std::fs::write(&marker, FORMAT)?;
        }
        let contract = Contract::bundled().map_err(|e| StoreError::Contract(e.to_string()))?;
        let chassis = DbHandle::open(
            &home.join("metaform.lbug"),
            "metaform-chassis-writer".into(),
        )?;
        registry::create_schema(&chassis.db)?;
        Ok(Store {
            dbs: Mutex::default(),
            max_open: max_open.max(1),
            chassis,
            subscribers: Arc::default(),
            contract: Arc::new(contract),
            settings,
            defined: Mutex::default(),
            home: home.to_path_buf(),
            _owner: owner,
        })
    }

    /// Register a project folder under `name`, or return the id it already has. The id names
    /// its folder under `projects/`. Nothing is written into the project's own folder.
    pub fn register_project(&self, source: &Path, name: &str) -> Result<String, StoreError> {
        let source = std::fs::canonicalize(source)?;
        let (reply, answer) = mpsc::sync_channel(1);
        let home = self.home.clone();
        let name = name.to_string();
        self.chassis.writer.submit(Job {
            client: ClientId(0),
            task: Box::new(move |conn| {
                let _ = reply.send(registry::register(conn, &home, &source, &name));
            }),
        })?;
        answer.recv().map_err(|_| StoreError::WriterGone)?
    }

    /// Every project registered in this home (the chassis registry), by name. Registers nothing.
    pub fn projects(&self) -> Result<Vec<Registered>, StoreError> {
        registry::list(&self.chassis.db)
    }

    /// The registered project id for a source folder, if any.
    pub fn find_project(&self, source: &Path) -> Result<Option<String>, StoreError> {
        let source = std::fs::canonicalize(source)?;
        registry::find(&self.chassis.db, &source)
    }

    /// The one Metaform tool's definition (name, description, input schema) from the contract.
    pub fn tool_definition(&self) -> Value {
        self.contract.tool().clone()
    }

    /// Perform one command of the Metaform tool on a map.
    pub fn execute(
        &self,
        client: ClientId,
        map: &MapKey,
        command: &Value,
    ) -> Result<Value, Failure> {
        self.ensure_defined(map)?;
        let db = self.db(&map.db)?;
        let verb = command
            .as_object()
            .and_then(|o| o.keys().next())
            .map(String::as_str);
        // A ref inside the project is stored relative to the project folder, so the map holds
        // when the folder moves. A map that belongs to no project has no folder to be relative to.
        if let DbKey::Project(id) = &map.db
            && let Some(project) = self.projects()?.into_iter().find(|project| &project.id == id)
        {
            metaform_core::refs::check_relative(command, &project.folder).map_err(Failure::Refused)?;
        }
        if !matches!(verb, Some("add" | "update" | "delete")) {
            let snapshot = db.snapshot(&map.map)?;
            return match metaform_core::execute(&self.contract, &snapshot, command) {
                Ok(outcome) => Ok(outcome.result().clone()),
                Err(refusal) => Err(Failure::Refused(refusal)),
            };
        }
        let (reply, answer) = mpsc::sync_channel(1);
        let (snapshots, contract, subscribers) = (
            Arc::clone(&db.snapshots),
            Arc::clone(&self.contract),
            Arc::clone(&self.subscribers),
        );
        let (key, command) = (map.clone(), command.clone());
        db.writer.submit(Job {
            client,
            task: Box::new(move |conn| {
                let result = write(conn, &snapshots, &contract, &subscribers, &key, &command);
                let _ = reply.send(result);
            }),
        })?;
        answer
            .recv()
            .map_err(|_| Failure::Store(StoreError::WriterGone))?
    }

    /// Run several commands of the Metaform tool against one map as one write: each is checked
    /// against the map the ones before it made, and all are stored in one transaction, or none
    /// are. No other client's write lands between them. Returns each command's result in order.
    /// For writes that must not be split, such as a specification import.
    pub fn execute_all(
        &self,
        client: ClientId,
        map: &MapKey,
        commands: &[Value],
    ) -> Result<Vec<Value>, BatchFailure> {
        let whole = |failure: Failure| BatchFailure { index: None, failure };
        self.ensure_defined(map).map_err(|e| whole(e.into()))?;
        let db = self.db(&map.db).map_err(|e| whole(e.into()))?;
        let (reply, answer) = mpsc::sync_channel(1);
        let (snapshots, contract, subscribers) = (
            Arc::clone(&db.snapshots),
            Arc::clone(&self.contract),
            Arc::clone(&self.subscribers),
        );
        let (key, commands) = (map.clone(), commands.to_vec());
        db.writer
            .submit(Job {
                client,
                task: Box::new(move |conn| {
                    let result =
                        write_all(conn, &snapshots, &contract, &subscribers, &key, &commands);
                    let _ = reply.send(result);
                }),
            })
            .map_err(|e| whole(e.into()))?;
        answer
            .recv()
            .map_err(|_| whole(Failure::Store(StoreError::WriterGone)))?
    }

    /// The current map, for reads outside the tool such as the CLI's specification export. The
    /// server stays the only reader and writer of the store (R-4.4).
    pub fn snapshot(&self, map: &MapKey) -> Result<Arc<Map>, StoreError> {
        self.ensure_defined(map)?;
        self.db(&map.db)?.snapshot(&map.map)
    }

    /// Make a project's main map hold the server-defined layer definitions exactly as the code
    /// defines them (R-6.24): today the specification layer at
    /// `specification::DEFINITION_ADDRESS`. Runs once per main map per server run, before its
    /// first command or snapshot, so `goto` and the export always find the layer and the stored
    /// definition follows the code. Standalone maps are left alone: nothing exports them, and
    /// in-world private maps (R-4.15) get no project definitions.
    ///
    /// The write goes through the writer and core like any command, so it is checked, committed
    /// in one transaction and announced. When the definition is already current it writes
    /// nothing. Two first touches at once each send a job; the second finds it current.
    pub fn ensure_defined(&self, map: &MapKey) -> Result<(), StoreError> {
        if !map.is_main() {
            return Ok(());
        }
        if self.defined.lock().expect("defined lock").contains(map) {
            return Ok(());
        }
        let db = self.db(&map.db)?;
        let (reply, answer) = mpsc::sync_channel(1);
        let (snapshots, contract, subscribers) = (
            Arc::clone(&db.snapshots),
            Arc::clone(&self.contract),
            Arc::clone(&self.subscribers),
        );
        let key = map.clone();
        db.writer.submit(Job {
            client: ClientId(0),
            task: Box::new(move |conn| {
                let result = load_into(&snapshots, conn, &key.map).and_then(|current| {
                    let Some(command) = definition_command(&current) else {
                        return Ok(());
                    };
                    match write(conn, &snapshots, &contract, &subscribers, &key, &command) {
                        Ok(_) => Ok(()),
                        Err(Failure::Store(e)) => Err(e),
                        Err(Failure::Refused(refusal)) => Err(StoreError::Definition(format!(
                            "{}: {:?}",
                            specification::DEFINITION_ADDRESS,
                            refusal
                        ))),
                    }
                });
                let _ = reply.send(result);
            }),
        })?;
        answer.recv().map_err(|_| StoreError::WriterGone)??;
        self.defined
            .lock()
            .expect("defined lock")
            .insert(map.clone());
        Ok(())
    }

    /// Diagnostic: the problems in a map's stored graph shape (R-4.16), or none. For the
    /// operator's view and tests; agents never see it.
    pub fn check_graph(&self, map: &MapKey) -> Result<Vec<String>, StoreError> {
        let db = self.db(&map.db)?;
        let conn = lbug::Connection::new(&db.db)?;
        graph::check(&conn, &map.map)
    }

    /// Receive an announcement after each commit to `map`. The subscriber is removed at the
    /// first commit after the receiver is dropped; use `watch` to remove it at once.
    pub fn subscribe(&self, map: &MapKey) -> mpsc::Receiver<Announcement> {
        let (send, recv) = mpsc::channel();
        self.register(map, Box::new(move |a| send.send(a.clone()).is_ok()));
        recv
    }

    /// Call `sink` after each commit to `map`, on the writer thread, until the returned `Watch`
    /// is dropped or `sink` returns false. `sink` must not block: hand the announcement to a
    /// channel and return.
    pub fn watch(&self, map: &MapKey, sink: Sink) -> Watch {
        let id = self.register(map, sink);
        Watch { id, subscribers: Arc::downgrade(&self.subscribers) }
    }

    fn register(&self, map: &MapKey, sink: Sink) -> u64 {
        let mut list = self.subscribers.lock().expect("subscriber lock");
        list.next += 1;
        let id = list.next;
        list.entries.push((id, map.clone(), sink));
        id
    }

    /// How many grouping databases are open now, for the operator's view.
    pub fn open_databases(&self) -> usize {
        self.dbs.lock().expect("database lock").handles.len()
    }

    fn db(&self, key: &DbKey) -> Result<Arc<DbHandle>, StoreError> {
        let mut dbs = self.dbs.lock().expect("database lock");
        dbs.tick += 1;
        let tick = dbs.tick;
        if let Some((found, used)) = dbs.handles.get_mut(key) {
            *used = tick;
            return Ok(Arc::clone(found));
        }
        let path = match key {
            DbKey::Project(id) => {
                if registry::source_of(&self.chassis.db, id)?.is_none() {
                    return Err(StoreError::UnknownProject(id.clone()));
                }
                self.home.join("projects").join(id).join("project.lbug")
            }
            DbKey::Standalone => self.home.join("maps").join("maps.lbug"),
        };
        // Close idle databases first. A handle only this map holds has no command in flight,
        // so its writer's queue is empty. Dropping it ends the writer and closes the database
        // before another database opens.
        while dbs.handles.len() >= self.max_open {
            let idle = dbs
                .handles
                .iter()
                .filter(|(_, (handle, _))| Arc::strong_count(handle) == 1)
                .min_by_key(|(_, (_, used))| *used)
                .map(|(k, _)| k.clone());
            match idle {
                Some(k) => drop(dbs.handles.remove(&k)),
                None => break, // every open database is busy; go over the limit briefly
            }
        }
        let handle = Arc::new(DbHandle::open(&path, format!("metaform-writer-{tick}"))?);
        dbs.handles.insert(key.clone(), (Arc::clone(&handle), tick));
        Ok(handle)
    }
}

/// The body of one write job, on the writer thread: one command.
fn write(
    conn: &lbug::Connection,
    snapshots: &Snapshots,
    contract: &Contract,
    subscribers: &Subscribers,
    key: &MapKey,
    command: &Value,
) -> Result<Value, Failure> {
    write_all(conn, snapshots, contract, subscribers, key, std::slice::from_ref(command))
        .map(|mut results| results.remove(0))
        .map_err(|failed| failed.failure)
}

/// The body of one write job, on the writer thread: every command in order, each checked against
/// the map the ones before it made. All the changes are stored in one transaction and announced
/// once, or none are. The job holds the writer, so no other write lands between the commands.
fn write_all(
    conn: &lbug::Connection,
    snapshots: &Snapshots,
    contract: &Contract,
    subscribers: &Subscribers,
    key: &MapKey,
    commands: &[Value],
) -> Result<Vec<Value>, BatchFailure> {
    let whole = |failure: Failure| BatchFailure { index: None, failure };
    let mut map = load_into(snapshots, conn, &key.map).map_err(|e| whole(e.into()))?;
    let before = Arc::clone(&map);
    let mut effect = Effect::default();
    let mut results = Vec::with_capacity(commands.len());
    for (index, command) in commands.iter().enumerate() {
        match metaform_core::execute(contract, &map, command) {
            Err(refusal) => {
                return Err(BatchFailure {
                    index: Some(index),
                    failure: Failure::Refused(refusal),
                });
            }
            Ok(Outcome::Read(result)) => results.push(result),
            Ok(Outcome::Write(write)) => {
                // Each entry is the element's state after its command, so a later entry for
                // the same address replaces an earlier one.
                effect.elements.extend(write.effect.elements);
                map = Arc::new(write.map);
                results.push(write.result);
            }
        }
    }
    if effect.is_empty() {
        return Ok(results);
    }
    writer::transact(conn, |c| graph::persist(c, &key.map, &before, &effect))
        .map_err(|e| whole(e.into()))?;
    snapshots
        .write()
        .expect("snapshot lock")
        .insert(key.map.clone(), map);
    let changed = effect.to_json();
    let announcement = Announcement { map: key.clone(), changed };
    subscribers
        .lock()
        .expect("subscriber lock")
        .entries
        .retain(|(_, map, sink)| map != key || sink(&announcement));
    Ok(results)
}

/// The `update` that makes the map's specification layer definition equal to
/// `specification::definition()`, or `None` when it already is. `update` merges fields, so a
/// stored field the definition no longer has is removed with `null` (R-5.5).
fn definition_command(map: &Map) -> Option<Value> {
    let wanted = specification::definition();
    let current = map.element(specification::DEFINITION_ADDRESS);
    if current.is_some_and(|e| e.fields == wanted) {
        return None;
    }
    let mut fields = wanted.clone();
    for key in current.into_iter().flat_map(|e| e.fields.keys()) {
        if !wanted.contains_key(key) {
            fields.insert(key.clone(), Value::Null);
        }
    }
    Some(json!({"update": {specification::DEFINITION_ADDRESS: fields}}))
}

/// The JSON an agent receives for a refusal.
pub fn refusal_json(command: &Value, refusal: &Refusal) -> Value {
    let mut out = command.as_object().cloned().unwrap_or_default();
    out.insert("status".into(), json!("error"));
    if let Value::Object(fields) = refusal.to_json() {
        out.extend(fields);
    }
    Value::Object(out)
}

/// A store failure as an agent receives it: the same structure as a refusal, with the code
/// `INTERNAL_ERROR` (server design, Isolation). The message is the store's own, followed by what
/// to do before a retry: a write may have been stored before the failure, and a repeated `add`
/// can duplicate entries.
pub fn store_failure_json(command: &Value, error: &StoreError) -> Value {
    let message = match error {
        // Refused on open, before any write: nothing can have been stored.
        StoreError::Schema(_) => format!("{error}."),
        _ => format!(
            "{error}. A write may or may not be stored; read the element before you retry it."
        ),
    };
    refusal_json(command, &Refusal::new(Code::InternalError, message, None))
}
