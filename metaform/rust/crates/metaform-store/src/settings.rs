//! Settings (R-4.8): every setting is declared here with its default, and a default is never
//! stored. A global value lives in `<home>/settings.json`; a project's value overrides it and lives
//! in `projects/<id>/settings.json`, beside the project's database (R-4.1: settings may be JSON).
//! Every lookup goes through [`Settings::get`].
//!
//! Only the functional map server writes these files (R-4.4); the CLI reads and sets values through
//! it (`metaform settings`, `metaform set`), never through an agent tool. A file is rewritten whole
//! through a temporary file and a rename, so a crash leaves the old file or the new one. A key the
//! code does not declare, or a value of the wrong kind, is refused when set; one found in a file at
//! load is reported and ignored, so a stale file never stops the server.

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use std::sync::Mutex;

use serde_json::{Value, json};

/// One declared setting.
pub struct Setting {
    pub key: &'static str,
    pub about: &'static str,
    /// Read only when the server starts, so a change applies at the next start.
    pub at_start: bool,
    /// Global only: a project cannot override it.
    pub global_only: bool,
    default: fn() -> Value,
    check: fn(&Value) -> Result<(), String>,
}

impl Setting {
    pub fn default_value(&self) -> Value {
        (self.default)()
    }
}

fn whole_number_from_one(value: &Value) -> Result<(), String> {
    match value.as_u64() {
        Some(n) if n >= 1 => Ok(()),
        _ => Err("must be a whole number, at least 1".into()),
    }
}

/// Every setting the server has.
pub const SETTINGS: &[Setting] = &[Setting {
    key: "stores.max_open_databases",
    about: "Databases kept open at once; the least recently used closes first. Each holds about 28 MB (docs/designs/storage.md, risk 5).",
    at_start: true,
    global_only: true,
    default: || json!(crate::DEFAULT_MAX_OPEN),
    check: whole_number_from_one,
}];

/// The declared setting for a key.
pub fn declared(key: &str) -> Option<&'static Setting> {
    SETTINGS.iter().find(|s| s.key == key)
}

/// Where a setting's value came from.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Source {
    Default,
    Global,
    Project,
}

type Values = BTreeMap<String, Value>;

/// The home's settings: the global file, and each project's file once read.
pub struct Settings {
    home: PathBuf,
    global: Mutex<Values>,
    projects: Mutex<BTreeMap<String, Values>>,
}

impl Settings {
    /// Read the global file. Problems in it are reported on stderr and the entries ignored.
    pub fn load(home: &Path) -> Settings {
        let global = read(&home.join(SETTINGS_FILE), false);
        Settings { home: home.to_path_buf(), global: Mutex::new(global), projects: Mutex::default() }
    }

    /// A setting's value for `project` (or globally), and where it came from.
    pub fn get(&self, key: &str, project: Option<&str>) -> Option<(Value, Source)> {
        let setting = declared(key)?;
        if let Some(id) = project.filter(|_| !setting.global_only)
            && let Some(value) = self.project_values(id).get(key)
        {
            return Some((value.clone(), Source::Project));
        }
        if let Some(value) = self.global.lock().expect("settings lock").get(key) {
            return Some((value.clone(), Source::Global));
        }
        Some((setting.default_value(), Source::Default))
    }

    /// Every setting's value for `project` (or globally), with its default and source.
    pub fn list(&self, project: Option<&str>) -> Value {
        let rows: Vec<Value> = SETTINGS
            .iter()
            .map(|s| {
                let (value, source) = self.get(s.key, project).expect("declared");
                json!({"key": s.key, "value": value, "default": s.default_value(), "source": format!("{source:?}").to_lowercase(),
                       "about": s.about, "applies": if s.at_start { "at the next start" } else { "at once" }})
            })
            .collect();
        json!(rows)
    }

    /// Set a value globally or for `project`, or remove it (`None`) so the next level applies.
    /// Refused for an undeclared key, a value of the wrong kind, or a global-only key set for a
    /// project.
    pub fn set(&self, key: &str, value: Option<Value>, project: Option<&str>) -> Result<(), String> {
        let setting = declared(key).ok_or_else(|| {
            let known: Vec<&str> = SETTINGS.iter().map(|s| s.key).collect();
            format!("there is no setting {key:?}; the settings are {}", known.join(", "))
        })?;
        if let Some(value) = &value {
            (setting.check)(value).map_err(|why| format!("{key} {why}"))?;
        }
        if project.is_some() && setting.global_only {
            return Err(format!("{key} is global only; set it without a project"));
        }
        let path = match project {
            Some(id) => self.home.join("projects").join(id).join(SETTINGS_FILE),
            None => self.home.join(SETTINGS_FILE),
        };
        let mut values = match project {
            Some(id) => self.project_values(id),
            None => self.global.lock().expect("settings lock").clone(),
        };
        match value {
            Some(value) => values.insert(key.to_string(), value),
            None => values.remove(key),
        };
        write(&path, &values).map_err(|e| format!("{}: {e}", path.display()))?;
        match project {
            Some(id) => self.projects.lock().expect("settings lock").insert(id.to_string(), values),
            None => Some(std::mem::replace(&mut *self.global.lock().expect("settings lock"), values)),
        };
        Ok(())
    }

    fn project_values(&self, id: &str) -> Values {
        let mut projects = self.projects.lock().expect("settings lock");
        projects.entry(id.to_string()).or_insert_with(|| read(&self.home.join("projects").join(id).join(SETTINGS_FILE), true)).clone()
    }
}

/// The settings file's name, globally and in each project's folder under the home.
pub const SETTINGS_FILE: &str = "settings.json";

/// Read a settings file: declared keys with valid values only, the rest reported and ignored.
fn read(path: &Path, project: bool) -> Values {
    let Ok(text) = std::fs::read_to_string(path) else { return Values::new() };
    let Ok(Value::Object(entries)) = serde_json::from_str::<Value>(&text) else {
        eprintln!("metaform: {} is not a JSON object; its settings are ignored", path.display());
        return Values::new();
    };
    let mut values = Values::new();
    for (key, value) in entries {
        match declared(&key) {
            None => eprintln!("metaform: {}: there is no setting {key:?}; ignored", path.display()),
            Some(s) if project && s.global_only => eprintln!("metaform: {}: {key} is global only; ignored here", path.display()),
            Some(s) => match (s.check)(&value) {
                Ok(()) => {
                    values.insert(key, value);
                }
                Err(why) => eprintln!("metaform: {}: {key} {why}; the default applies", path.display()),
            },
        }
    }
    values
}

/// Write a settings file whole: a temporary file, synced, then renamed over the old one.
fn write(path: &Path, values: &Values) -> std::io::Result<()> {
    if let Some(dir) = path.parent() {
        std::fs::create_dir_all(dir)?;
    }
    let temporary = path.with_extension("json.tmp");
    {
        let mut file = std::fs::File::create(&temporary)?;
        std::io::Write::write_all(&mut file, serde_json::to_string_pretty(values).expect("JSON values encode").as_bytes())?;
        file.sync_all()?;
    }
    std::fs::rename(&temporary, path)
}
