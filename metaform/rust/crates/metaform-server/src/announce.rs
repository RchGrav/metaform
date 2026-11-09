//! Announcements (R-4.10): the connection's map as one MCP resource, and a push to every
//! subscriber after each commit to that map, by any agent. Nothing polls.
//!
//! - MCP 2026-07-28 clients open `subscriptions/listen` with the map's URI in
//!   `resourceSubscriptions`; rmcp 3.9 supports it (`accepted_subscription_filter`, `listen`).
//! - Older clients use `resources/subscribe`, which rmcp routes only for them.
//!
//! Both are fed by `Store::watch`, which calls back only after a write commits (R-4.7), so a
//! notification never announces a change a read could not yet see.

use metaform_store::{DbKey, MapKey, Store, Watch};
use tokio::sync::mpsc::{UnboundedReceiver, unbounded_channel};

/// The URI that names a map across every connection to the home:
/// `metaform://map/project/<project id>/<map>` or `metaform://map/standalone/<map>`.
pub fn map_uri(map: &MapKey) -> String {
    match &map.db {
        DbKey::Project(id) => format!("metaform://map/project/{id}/{}", map.map),
        DbKey::Standalone => format!("metaform://map/standalone/{}", map.map),
    }
}

/// A live feed of commits to one map. Dropping it unsubscribes at once (`Store::watch`), so a
/// quiet map holds no thread and no stale subscriber.
pub struct Feed {
    recv: UnboundedReceiver<()>,
    _watch: Watch,
}

impl Feed {
    /// The next commit, or None once the store has closed.
    pub async fn next(&mut self) -> Option<()> {
        self.recv.recv().await
    }
}

/// Start a feed for `map`, from the moment this is called. The store calls the sink on its
/// writer thread after each commit; the sink only hands a tick to a tokio channel.
pub fn changes(store: &Store, map: &MapKey) -> Feed {
    let (send, recv) = unbounded_channel();
    let watch = store.watch(map, Box::new(move |_| send.send(()).is_ok()));
    Feed {
        recv,
        _watch: watch,
    }
}
