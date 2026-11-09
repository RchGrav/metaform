//! The write manager (R-4.7, `docs/designs/storage.md` 2.5).
//!
//! One writer thread for each database holds that database's only writing connection. On
//! lbug 0.22.3 a second writing connection is worse than refused: a write after a refused
//! transaction ended the process. Every write is a job sent to the writer.
//!
//! Jobs wait in a queue for each client. The writer serves the clients in turn, one job at
//! a time, so a client that sends many writes at once cannot starve another. Each job runs
//! its own transaction and answers after commit.

use std::collections::{HashMap, VecDeque};
use std::sync::Arc;
use std::sync::mpsc;
use std::thread::JoinHandle;

use lbug::{Connection, Database};

use crate::{ClientId, StoreError};

pub(crate) type Task = Box<dyn FnOnce(&Connection) + Send>;

pub(crate) struct Job {
    pub client: ClientId,
    pub task: Task,
}

/// A running writer. Dropping it stops the thread after the queued jobs finish.
pub(crate) struct Writer {
    queue: Option<mpsc::Sender<Job>>,
    thread: Option<JoinHandle<()>>,
}

impl Writer {
    pub fn start(db: Arc<Database>, name: String) -> Result<Writer, StoreError> {
        let (send, recv) = mpsc::channel::<Job>();
        let thread = std::thread::Builder::new().name(name).spawn(move || {
            let conn = match Connection::new(&db) {
                Ok(c) => c,
                Err(_) => return, // senders see a closed queue and report WriterGone
            };
            serve(&conn, &recv);
        })?;
        Ok(Writer {
            queue: Some(send),
            thread: Some(thread),
        })
    }

    pub fn submit(&self, job: Job) -> Result<(), StoreError> {
        self.queue
            .as_ref()
            .ok_or(StoreError::WriterGone)?
            .send(job)
            .map_err(|_| StoreError::WriterGone)
    }
}

impl Drop for Writer {
    fn drop(&mut self) {
        drop(self.queue.take());
        if let Some(thread) = self.thread.take() {
            let _ = thread.join();
        }
    }
}

/// Serve jobs fairly until every sender is gone.
fn serve(conn: &Connection, recv: &mpsc::Receiver<Job>) {
    let mut waiting: HashMap<ClientId, VecDeque<Task>> = HashMap::new();
    let mut turn: VecDeque<ClientId> = VecDeque::new();
    let add = |job: Job,
               waiting: &mut HashMap<ClientId, VecDeque<Task>>,
               turn: &mut VecDeque<ClientId>| {
        let queue = waiting.entry(job.client).or_default();
        if queue.is_empty() {
            turn.push_back(job.client);
        }
        queue.push_back(job.task);
    };
    loop {
        if turn.is_empty() {
            match recv.recv() {
                Ok(job) => add(job, &mut waiting, &mut turn),
                Err(_) => return,
            }
        }
        while let Ok(job) = recv.try_recv() {
            add(job, &mut waiting, &mut turn);
        }
        let client = turn.pop_front().expect("a client has work");
        let queue = waiting.get_mut(&client).expect("queue for client");
        let task = queue.pop_front().expect("queued task");
        if queue.is_empty() {
            waiting.remove(&client);
        } else {
            turn.push_back(client);
        }
        task(conn);
    }
}

/// Run `body` in one transaction on the writer's connection.
pub(crate) fn transact<T>(
    conn: &Connection,
    body: impl FnOnce(&Connection) -> Result<T, StoreError>,
) -> Result<T, StoreError> {
    conn.query("BEGIN TRANSACTION")?;
    match body(conn) {
        Ok(value) => {
            conn.query("COMMIT")?;
            Ok(value)
        }
        Err(e) => {
            let _ = conn.query("ROLLBACK");
            Err(e)
        }
    }
}
