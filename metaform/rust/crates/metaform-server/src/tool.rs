//! The one Metaform tool over MCP. The definition comes from the contract
//! (`metaform/mcp-tools.proposed.json`); this file adds no tool and changes no schema.

use std::borrow::Cow;
use std::collections::HashMap;
use std::sync::{Arc, Mutex};

use metaform_store::{ClientId, Failure, MapKey, Store, refusal_json, store_failure_json};
use rmcp::ErrorData;
use rmcp::handler::server::ServerHandler;
use rmcp::model::{
    CallToolRequestParams, CallToolResponse, CallToolResult, ContentBlock, Implementation,
    ListResourcesResult, ListToolsResult, PaginatedRequestParams, ReadResourceRequestParams,
    ReadResourceResponse, ReadResourceResult, Resource, ResourceContents,
    ResourceUpdatedNotificationParam, ServerCapabilities, ServerConfig, SubscribeRequestParams,
    SubscriptionFilter, Tool, UnsubscribeRequestParams,
};
use rmcp::service::{RequestContext, RoleServer, SubscriptionContext};

use crate::announce;
use serde_json::Value;

/// One agent's connection: its client id, the map it works on, and the shared store. Until
/// agent identity exists, the connection stands for the agent and its context (R-5.30, R-8.2).
pub struct MapTool {
    store: Arc<Store>,
    map: MapKey,
    client: ClientId,
    tool: Tool,
    presence: Mutex<Presence>,
    /// The map's resource URI (R-4.10).
    uri: String,
    /// Change feeds opened in `accepted_subscription_filter`, before rmcp acknowledges a
    /// listen, so no commit between the acknowledgement and `listen` is missed.
    pending: Mutex<Vec<announce::Feed>>,
    /// The task serving a legacy `resources/subscribe`, ended by `resources/unsubscribe`.
    legacy: Mutex<Option<tokio::task::AbortHandle>>,
}

/// Where the agent is, and what `goto` already delivered in this context.
#[derive(Default)]
struct Presence {
    at: Option<String>,
    delivered: HashMap<String, serde_json::Map<String, Value>>,
    /// Sheet parts that hold the same text at every address, delivered once per context rather
    /// than once per address: the layer `instructions` (R-6.27).
    once: serde_json::Map<String, Value>,
    /// Entries of `NAMED_AFTER_FIRST` parts already delivered in full in this context, by part.
    held: HashMap<String, serde_json::Map<String, Value>>,
}

/// Sheet parts whose entries are the same wherever they appear, so each entry is delivered once
/// per context.
const ONCE_PER_CONTEXT: [&str; 1] = ["instructions"];

/// Sheet parts whose entries can apply at many addresses: the `skills` frontmatter (R-5.30). Each
/// entry is delivered in full once per context. A later sheet that includes the part names an
/// entry the context already holds unchanged as `{}`, so the agent still sees what applies at the
/// address without receiving it again. A changed entry is delivered in full again.
const NAMED_AFTER_FIRST: [&str; 1] = ["skills"];

impl Presence {
    /// Record an arrival and return only the parts of the sheet not yet delivered unchanged in
    /// this context (R-5.30: "goto only dumps new info IF the info changes").
    fn arrive(&mut self, sheet: Value) -> Value {
        let Value::Object(sheet) = sheet else {
            return sheet;
        };
        let at = sheet
            .get("at")
            .and_then(Value::as_str)
            .unwrap_or_default()
            .to_string();
        let seen = self.delivered.entry(at.clone()).or_default();
        let mut out = serde_json::Map::new();
        out.insert("at".into(), Value::String(at.clone()));
        for (part, value) in sheet {
            if ONCE_PER_CONTEXT.contains(&part.as_str()) {
                let Value::Object(entries) = value else { continue };
                let fresh: serde_json::Map<String, Value> = entries
                    .into_iter()
                    .filter(|(name, text)| self.once.get(name) != Some(text))
                    .collect();
                if !fresh.is_empty() {
                    self.once.extend(fresh.clone());
                    out.insert(part, Value::Object(fresh));
                }
                continue;
            }
            if part == "at" || seen.get(&part) == Some(&value) {
                continue;
            }
            seen.insert(part.clone(), value.clone());
            if NAMED_AFTER_FIRST.contains(&part.as_str())
                && let Value::Object(entries) = value
            {
                let held = self.held.entry(part.clone()).or_default();
                let shown: serde_json::Map<String, Value> = entries
                    .into_iter()
                    .map(|(name, entry)| {
                        if held.get(&name) == Some(&entry) {
                            (name, Value::Object(serde_json::Map::new()))
                        } else {
                            held.insert(name.clone(), entry.clone());
                            (name, entry)
                        }
                    })
                    .collect();
                out.insert(part, Value::Object(shown));
                continue;
            }
            out.insert(part, value);
        }
        self.at = Some(at);
        Value::Object(out)
    }
}

impl MapTool {
    pub fn new(store: Arc<Store>, map: MapKey, client: ClientId) -> MapTool {
        let tool = tool_from(&store.tool_definition());
        MapTool {
            store,
            uri: announce::map_uri(&map),
            map,
            client,
            tool,
            presence: Mutex::default(),
            pending: Mutex::default(),
            legacy: Mutex::default(),
        }
    }
}

/// Build the MCP tool from the contract's definition.
pub fn tool_from(definition: &Value) -> Tool {
    let text = |key: &str| {
        definition
            .get(key)
            .and_then(Value::as_str)
            .unwrap_or_default()
            .to_string()
    };
    let schema = match definition.get("inputSchema") {
        Some(Value::Object(schema)) => schema.clone(),
        _ => serde_json::Map::new(),
    };
    Tool::new(
        Cow::Owned(text("name")),
        Cow::Owned(text("description")),
        Arc::new(schema),
    )
}

impl ServerHandler for MapTool {
    fn get_info(&self) -> ServerConfig {
        let mut info = ServerConfig::default();
        info.capabilities = ServerCapabilities::builder()
            .enable_tools()
            .enable_resources()
            .enable_resources_subscribe()
            .build();
        info.server_info = Implementation::new("metaform", env!("CARGO_PKG_VERSION"));
        info
    }

    async fn list_tools(
        &self,
        _request: Option<PaginatedRequestParams>,
        _context: RequestContext<RoleServer>,
    ) -> Result<ListToolsResult, ErrorData> {
        Ok(ListToolsResult::with_all_items(vec![self.tool.clone()]))
    }

    /// One resource: this connection's map. Reading it gives the shallow graph, `{"map": {}}`.
    async fn list_resources(
        &self,
        _request: Option<PaginatedRequestParams>,
        _context: RequestContext<RoleServer>,
    ) -> Result<ListResourcesResult, ErrorData> {
        let map = Resource::new(self.uri.clone(), "map").with_description(
            "This connection's functional map. Reading it returns the shallow graph: every address \
             and every want as an edge. Subscribe to hear of each commit.",
        );
        Ok(ListResourcesResult::with_all_items(vec![map]))
    }

    async fn read_resource(
        &self,
        request: ReadResourceRequestParams,
        _context: RequestContext<RoleServer>,
    ) -> Result<ReadResourceResponse, ErrorData> {
        if request.uri != self.uri {
            return Err(ErrorData::invalid_params(
                format!(
                    "unknown resource {}; this connection's map is {}",
                    request.uri, self.uri
                ),
                None,
            ));
        }
        let (store, map, client) = (Arc::clone(&self.store), self.map.clone(), self.client);
        let root = tokio::task::spawn_blocking(move || {
            store.execute(client, &map, &serde_json::json!({"map": {}}))
        })
        .await
        .map_err(|e| ErrorData::internal_error(e.to_string(), None))?
        .map_err(|e| ErrorData::internal_error(format!("{e:?}"), None))?;
        let contents = ResourceContents::text(root.to_string(), self.uri.clone());
        Ok(ReadResourceResult::new(vec![contents]).into())
    }

    /// Accept this connection's map URI and nothing else. The feed starts here, before rmcp
    /// acknowledges the listen, so a commit right after the acknowledgement is not missed.
    fn accepted_subscription_filter(
        &self,
        requested: &SubscriptionFilter,
    ) -> Option<SubscriptionFilter> {
        let mut accepted = SubscriptionFilter::new();
        let wanted = requested
            .resource_subscriptions
            .as_ref()
            .is_some_and(|u| u.contains(&self.uri));
        if wanted {
            accepted.resource_subscriptions = Some(vec![self.uri.clone()]);
            let feed = announce::changes(&self.store, &self.map);
            self.pending.lock().expect("pending lock").push(feed);
        }
        Some(accepted)
    }

    /// Push `notifications/resources/updated` after each commit to the map, until the client
    /// cancels the listen or the store closes.
    async fn listen(&self, context: SubscriptionContext) -> Result<(), ErrorData> {
        let wanted = context
            .accepted()
            .resource_subscriptions
            .as_ref()
            .is_some_and(|u| u.contains(&self.uri));
        let feed = if wanted {
            self.pending.lock().expect("pending lock").pop()
        } else {
            None
        };
        let Some(mut feed) = feed else {
            context.cancelled().await;
            return Ok(());
        };
        loop {
            tokio::select! {
                _ = context.cancelled() => return Ok(()),
                tick = feed.next() => match tick {
                    Some(()) => {
                        if context.sink().notify_resource_updated(self.uri.clone()).await.is_err() {
                            return Ok(());
                        }
                    }
                    None => return Ok(()),
                },
            }
        }
    }

    /// The same push for clients older than 2026-07-28, through `resources/subscribe`.
    #[allow(deprecated)]
    async fn subscribe(
        &self,
        request: SubscribeRequestParams,
        context: RequestContext<RoleServer>,
    ) -> Result<(), ErrorData> {
        if request.uri != self.uri {
            return Err(ErrorData::invalid_params(
                format!("unknown resource {}", request.uri),
                None,
            ));
        }
        let mut feed = announce::changes(&self.store, &self.map);
        let (peer, uri) = (context.peer.clone(), self.uri.clone());
        let task = tokio::spawn(async move {
            while feed.next().await.is_some() {
                let updated = ResourceUpdatedNotificationParam::new(uri.clone());
                if peer.notify_resource_updated(updated).await.is_err() {
                    break;
                }
            }
        });
        if let Some(old) = self
            .legacy
            .lock()
            .expect("legacy lock")
            .replace(task.abort_handle())
        {
            old.abort();
        }
        Ok(())
    }

    #[allow(deprecated)]
    async fn unsubscribe(
        &self,
        _request: UnsubscribeRequestParams,
        _context: RequestContext<RoleServer>,
    ) -> Result<(), ErrorData> {
        if let Some(task) = self.legacy.lock().expect("legacy lock").take() {
            task.abort();
        }
        Ok(())
    }

    async fn call_tool(
        &self,
        request: CallToolRequestParams,
        _context: RequestContext<RoleServer>,
    ) -> Result<CallToolResponse, ErrorData> {
        let command = Value::Object(request.arguments.unwrap_or_default());
        // MCP lists an unknown tool as a protocol error (JSON-RPC -32602), not a tool result.
        if request.name != self.tool.name {
            let message = format!(
                "unknown tool {}; the only tool is {}",
                request.name, self.tool.name
            );
            return Err(ErrorData::invalid_params(message, None));
        }
        let is_goto = command.get("goto").is_some();
        let (store, map, client) = (Arc::clone(&self.store), self.map.clone(), self.client);
        let sent = command.clone();
        let outcome = tokio::task::spawn_blocking(move || store.execute(client, &map, &sent))
            .await
            .map_err(|e| ErrorData::internal_error(e.to_string(), None))?;
        Ok(match outcome {
            Ok(result) => {
                let result = if is_goto {
                    self.presence.lock().expect("presence lock").arrive(result)
                } else {
                    result
                };
                CallToolResult::success(vec![ContentBlock::text(result.to_string())])
            }
            Err(Failure::Refused(refusal)) => {
                CallToolResult::error(vec![ContentBlock::text(refusal_json(&command, &refusal).to_string())])
            }
            Err(Failure::Store(e)) => {
                CallToolResult::error(vec![ContentBlock::text(store_failure_json(&command, &e).to_string())])
            }
        }
        .into())
    }
}
