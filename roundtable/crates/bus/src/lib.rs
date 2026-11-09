//! Typed in-process event bus.
//!
//! Rules this crate keeps, because the tools built on it depend on them:
//!
//! - **Never poll what can surface as an event.** State changes are published here; consumers
//!   await them.
//! - **Publishing never blocks.** A slow or stalled subscriber cannot stop a publisher. Each
//!   subscriber has its own unbounded queue, so nothing is dropped; the cost is that a subscriber
//!   that never reads holds its backlog in memory until it is dropped.
//! - **One global order.** Every event gets a sequence number, and every subscriber receives
//!   events in sequence order, whatever their type.
//! - **No dependency on an async runtime.** Receiving uses `futures` channels, which work under
//!   tokio, smol or Bevy's executor alike.
//!
//! A [`Subscription`] receives one event type. A [`Tap`] receives every event as an
//! [`Envelope`], which can render its payload as JSON for recording or display.

use std::any::{Any, TypeId};
use std::collections::HashMap;
use std::fmt::Debug;
use std::pin::Pin;
use std::sync::{Arc, Mutex, OnceLock};
use std::task::{Context, Poll};
use std::time::SystemTime;

use futures::channel::mpsc::{UnboundedReceiver, UnboundedSender, unbounded};
use futures::{Stream, StreamExt};
use serde::Serialize;

/// Something that can be published on the bus.
///
/// `NAME` is the stable, human-readable event name used in records and on the wire, for
/// example `"acp.session.update"`. Keep it unique across the program.
pub trait Event: Any + Send + Sync + Debug + Serialize {
    const NAME: &'static str;
}

/// One published event, as a tap sees it.
#[derive(Clone)]
pub struct Envelope {
    /// Position in the bus's global order, starting at 1.
    pub seq: u64,
    /// Wall-clock time of publication.
    pub at: SystemTime,
    /// The event's [`Event::NAME`].
    pub name: &'static str,
    payload: Arc<dyn Payload>,
    json: Arc<OnceLock<Option<serde_json::Value>>>,
}

impl Envelope {
    /// The payload as JSON. Serialized once per event, on first request, and shared by
    /// every tap that asks.
    pub fn to_json(&self) -> serde_json::Result<serde_json::Value> {
        let cached = self.json.get_or_init(|| self.payload.to_json().ok());
        match cached {
            Some(value) => Ok(value.clone()),
            None => self.payload.to_json(),
        }
    }

    /// The payload as its concrete type, if it is an `E`.
    pub fn downcast<E: Event>(&self) -> Option<&E> {
        self.payload.as_any().downcast_ref::<E>()
    }
}

impl Debug for Envelope {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Envelope")
            .field("seq", &self.seq)
            .field("name", &self.name)
            .field("payload", &self.payload)
            .finish()
    }
}

/// Type-erased view of an event, so taps can hold any event type.
trait Payload: Send + Sync + Debug {
    fn to_json(&self) -> serde_json::Result<serde_json::Value>;
    fn as_any(&self) -> &dyn Any;
}

impl<E: Event> Payload for E {
    fn to_json(&self) -> serde_json::Result<serde_json::Value> {
        serde_json::to_value(self)
    }
    fn as_any(&self) -> &dyn Any {
        self
    }
}

/// A received event of type `E`, with its place in the global order.
#[derive(Debug, Clone)]
pub struct Delivery<E> {
    pub seq: u64,
    pub at: SystemTime,
    pub event: Arc<E>,
}

type Erased = (u64, SystemTime, Arc<dyn Any + Send + Sync>);

#[derive(Default)]
struct Registry {
    seq: u64,
    /// Event names seen, with their types: a name must identify one type in records.
    names: HashMap<&'static str, TypeId>,
    typed: HashMap<TypeId, Vec<UnboundedSender<Erased>>>,
    taps: Vec<UnboundedSender<Envelope>>,
}

/// The event bus. Cloning it is cheap; every clone publishes to the same subscribers.
#[derive(Clone, Default)]
pub struct Bus {
    registry: Arc<Mutex<Registry>>,
}

impl Bus {
    pub fn new() -> Self {
        Self::default()
    }

    /// Publish an event to every current subscriber of its type and every tap.
    ///
    /// Returns the event's sequence number. Never blocks on subscribers; subscribers that have
    /// been dropped are removed here.
    pub fn publish<E: Event>(&self, event: E) -> u64 {
        let event = Arc::new(event);
        let at = SystemTime::now();
        // The lock covers numbering and enqueueing together, so concurrent publishers cannot
        // interleave and every queue receives events in sequence order.
        let mut registry = self.registry.lock().unwrap_or_else(|poisoned| poisoned.into_inner());
        registry.seq += 1;
        let seq = registry.seq;
        let known = *registry.names.entry(E::NAME).or_insert_with(TypeId::of::<E>);
        debug_assert!(known == TypeId::of::<E>(), "two event types share the name {}", E::NAME);

        if let Some(senders) = registry.typed.get_mut(&TypeId::of::<E>()) {
            let erased: Arc<dyn Any + Send + Sync> = event.clone();
            senders.retain(|sender| sender.unbounded_send((seq, at, erased.clone())).is_ok());
        }
        if !registry.taps.is_empty() {
            let envelope = Envelope { seq, at, name: E::NAME, payload: event, json: Arc::default() };
            registry.taps.retain(|tap| tap.unbounded_send(envelope.clone()).is_ok());
        }
        seq
    }

    /// Receive every event of type `E` published from now on.
    pub fn subscribe<E: Event>(&self) -> Subscription<E> {
        let (sender, receiver) = unbounded();
        let mut registry = self.registry.lock().unwrap_or_else(|poisoned| poisoned.into_inner());
        registry.typed.entry(TypeId::of::<E>()).or_default().push(sender);
        Subscription { receiver, _type: std::marker::PhantomData }
    }

    /// Receive every event of every type published from now on.
    pub fn tap(&self) -> Tap {
        let (sender, receiver) = unbounded();
        let mut registry = self.registry.lock().unwrap_or_else(|poisoned| poisoned.into_inner());
        registry.taps.push(sender);
        Tap { receiver }
    }
}

/// Events of one type, in publication order. Ends only when every [`Bus`] clone is dropped.
pub struct Subscription<E> {
    receiver: UnboundedReceiver<Erased>,
    _type: std::marker::PhantomData<fn() -> E>,
}

impl<E: Event> Subscription<E> {
    /// Wait for the next event. `None` means the bus is gone.
    pub async fn recv(&mut self) -> Option<Delivery<E>> {
        self.next().await
    }
}

impl<E: Event> Stream for Subscription<E> {
    type Item = Delivery<E>;

    fn poll_next(mut self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Option<Self::Item>> {
        self.receiver.poll_next_unpin(cx).map(|item| {
            item.map(|(seq, at, event)| Delivery {
                seq,
                at,
                // Only events of type E are ever queued for this subscription.
                event: event.downcast::<E>().expect("subscription received a foreign event type"),
            })
        })
    }
}

/// Every event, in publication order. Ends only when every [`Bus`] clone is dropped.
pub struct Tap {
    receiver: UnboundedReceiver<Envelope>,
}

impl Tap {
    /// Wait for the next event. `None` means the bus is gone.
    pub async fn recv(&mut self) -> Option<Envelope> {
        self.next().await
    }
}

impl Stream for Tap {
    type Item = Envelope;

    fn poll_next(mut self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Option<Self::Item>> {
        self.receiver.poll_next_unpin(cx)
    }
}
