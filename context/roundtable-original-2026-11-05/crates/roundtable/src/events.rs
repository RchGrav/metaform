//! Events a Roundtable publishes. The discussion record, the web interface and any chat
//! channel adapter are all built from these; none of them polls the engine.

use std::collections::BTreeMap;

use serde::Serialize;

use bus::Event;

macro_rules! event {
    ($name:ident, $wire:literal, { $($field:ident : $ty:ty),* $(,)? }) => {
        #[derive(Debug, Clone, Serialize)]
        pub struct $name { pub table: String, $(pub $field: $ty),* }
        impl Event for $name { const NAME: &'static str = $wire; }
    };
}

#[derive(Debug, Clone, Serialize)]
pub struct SeatInfo {
    pub name: String,
    pub harness: String,
    pub settings: BTreeMap<String, String>,
}

event!(TableOpened, "roundtable.opened", {
    objective: String, topic: String, workspace: String, seats: Vec<SeatInfo>, judging: bool, jev_configured: bool, base_allowance: Option<usize>,
    recovery_allowance: usize, rounds: Option<u64>,
});
event!(SeatReady, "roundtable.seat.ready", {
    seat: String,
    name: String,
    session: String,
    tools: bool,
    protocol: u16,
});
event!(SeatFailed, "roundtable.seat.failed", { seat: String, error: String });
event!(SeatGone, "roundtable.seat.gone", { seat: String, detail: String });
event!(FloorGiven, "roundtable.floor", { seat: String, round: u64, allowance: Option<usize> });
event!(Contribution, "roundtable.contribution", {
    seat: String,
    id: Option<String>,
    text: String,
    accepted: bool,
    judged: bool,
    scores: BTreeMap<String, f64>,
    reasons: Vec<String>,
    limit: Option<usize>,
    after_work: bool,
    note: Option<String>,
});
event!(Passed, "roundtable.pass", { seat: String });
event!(WorkStarted, "roundtable.work.started", { seat: String });
event!(ReviewAsked, "roundtable.review", { seat: String });
event!(Skipped, "roundtable.skipped", { seat: String, reason: String });
event!(TurnFailed, "roundtable.turn.failed", { seat: String, error: String });
event!(RoundClosed, "roundtable.round", { round: u64, topic_may_advance: bool });
event!(TopicPolling, "roundtable.topic.polling", { seats: Vec<String> });
event!(TopicProposed, "roundtable.topic.proposed", { seat: String, text: String });
event!(TopicChanged, "roundtable.topic", { index: u64, topic: String, how: String, scores: Vec<(String, f64)> });
event!(ChairSpoke, "roundtable.chair", { text: String });
event!(Held, "roundtable.held", { held: bool });
event!(SettingsChanged, "roundtable.settings", { judging: bool, jev_configured: bool });
event!(FeedbackGiven, "roundtable.feedback", { from: String, from_name: String, to: String, to_name: String, to_session: String, ratings: BTreeMap<String, serde_json::Value>, note: String });
// An agent started or finished background work after its turn (ACP v2); `items` 0 is finished.
event!(BackgroundWork, "roundtable.background", { seat: String, items: usize });
event!(Notice, "roundtable.notice", { level: String, text: String });
event!(RatingsAsked, "roundtable.ratings.asked", { seats: Vec<String> });
// `to_session` is the rated agent's session: its identity. Genesis names can collide.
event!(RatingGiven, "roundtable.rating", {
    from: String,
    from_name: String,
    to: String,
    to_name: String,
    to_session: String,
    ratings: serde_json::Map<String, serde_json::Value>,
    points: f64,
});
event!(TableEnded, "roundtable.ended", { reason: String });
