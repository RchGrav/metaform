//! The table's state: seats, the discussion log, polls, judgements and the commands it takes.

use std::collections::{BTreeMap, HashMap, HashSet};
use std::sync::atomic::AtomicBool;
use std::sync::{Arc, Mutex};

use acp_host::Harness;
use bus::Bus;
use tokio::sync::mpsc;

use crate::config::TableConfig;
use crate::jev::Jev;
use crate::rules::RoundTracker;

/// The floor is offered only while at least this many participants are free (O).
pub const MIN_FREE_TO_DISCUSS: usize = 2;

/// A command from the chair or a participant tool.
#[derive(Debug, Clone)]
pub enum Command {
    Hold,
    Resume,
    /// Chair guidance: delivered to every participant with the other messages, never judged.
    Guidance(String),
    SetJevKey(Option<String>),
    /// End the current topic once the floor is free; with a topic, set it. Topics need JEV (O).
    Advance { by: String, topic: Option<String> },
    Feedback { from: String, to: String, ratings: BTreeMap<String, serde_json::Value>, note: String },
    /// First End: the rating round (O), then shutdown. End during the rating round: shutdown now.
    End,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum Activity {
    Idle,
    Floor(u64),
    Working(u64),
    Reviewing(u64),
    Proposing(u64),
    Rating(u64),
    /// Receiving one of the owner's scoring messages (receipt or results).
    Notified(u64),
}

impl Activity {
    pub(crate) fn prompt(self) -> Option<u64> {
        match self {
            Activity::Idle => None,
            Activity::Floor(p) | Activity::Working(p) | Activity::Reviewing(p) | Activity::Proposing(p) | Activity::Rating(p) | Activity::Notified(p) => Some(p),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum SeatState {
    Starting,
    Ready,
    Failed,
    Gone,
}

pub(crate) struct Seat {
    pub label: String,
    pub name: Option<String>,
    pub harness: Option<Harness>,
    pub session: String,
    pub state: SeatState,
    /// The reply limit of the discussion prompt it was last sent; `None` is no limit.
    pub limit: Option<usize>,
    /// It was skipped while busy, so its next discussion prompt gets the recovery limit once.
    pub recovery_due: bool,
    pub activity: Activity,
    pub prompt_topic: u64,
    /// Truncation and veto notices for the next turn, in the order they arose.
    pub notices: Vec<String>,
    /// The agent reports background work still running after its turn ended (ACP v2). D §5.2:
    /// "`idle` does not necessarily mean background work has ceased". It is working, so its
    /// discussion turns are skipped (R §4.4) until it reports none.
    pub background: bool,
    pub seen_log: usize,
    pub seen_topic: u64,
    pub first: bool,
    pub told_to_review: bool,
    /// Whether this seat was given Roundtable's tools (its harness accepts HTTP MCP).
    pub tools: bool,
    /// AgentSight observation of the harness process (R §10.2, D §8). Dropping it stops it.
    pub monitor: Option<agent_monitor::Monitor>,
}

/// The discussion everyone sees: accepted messages and chair guidance, in order.
/// `round` is the round the message was written in; JEV sees the last rounds by it.
pub(crate) enum Entry {
    Message { id: String, seat: String, name: String, text: String, round: u64 },
    Chair { text: String, round: u64 },
}

pub(crate) struct Judgement {
    pub seat: usize,
    pub text: String,
    /// The limit the message was measured against; `None` is no limit.
    pub limit: Option<usize>,
    pub after_work: bool,
    pub topic: u64,
    pub round: u64,
}

pub(crate) struct Polling {
    pub proposals: Vec<(usize, String)>,
    /// Seats asked in this poll: only their proposals count (not a late reply to an earlier poll).
    pub asked: HashSet<usize>,
    pub waiting: HashSet<usize>,
    /// Seats busy when the poll began: asked once their current prompt ends (R §7: "All
    /// participating agents are polled"; owner: "if everyone is busy the table has to wait").
    pub pending: HashSet<usize>,
    /// Set once the proposals went to JEV; the judged set is frozen from then on.
    pub scoring: Option<u64>,
}

pub(crate) enum Internal {
    SeatStarted { index: usize, result: Result<(Harness, String, bool, u16), String>, warnings: Vec<String> },
    Judged { ticket: u64, result: Result<BTreeMap<String, f64>, String> },
    Scored { ticket: u64, result: Result<BTreeMap<String, f64>, String> },
    Monitor { index: usize, result: Result<agent_monitor::Monitor, String> },
}

pub(crate) struct Table {
    pub id: String,
    pub cfg: TableConfig,
    pub bus: Bus,
    pub jev: Jev,
    pub seats: Vec<Seat>,
    pub topics: Vec<String>,
    pub topic_index: u64,
    pub log: Vec<Entry>,
    pub rounds: RoundTracker,
    pub round_no: u64,
    pub round_left: usize,
    pub cursor: usize,
    pub held: bool,
    pub ended: bool,
    pub floor: Option<(usize, u64)>,
    pub judgements: HashMap<u64, Judgement>,
    pub polling: Option<Polling>,
    /// The rating round: seats still to rate, and those already asked.
    /// A floor contribution is with JEV: the next turn waits for its answer, so the next
    /// agent sees an accepted message (owner's example, M: "Agent1 speaks ... agent2, 3, 4 all
    /// speak, when it comes back to agent 1 it is informed ... each agents message").
    pub judging_floor: Option<u64>,
    /// Where identity profiles are read from, if the host keeps them.
    pub identities: Option<Arc<dyn crate::config::Identities>>,
    /// Points and scorecard count each seat received at this table.
    pub session_points: BTreeMap<usize, (f64, usize)>,
    /// The results message, once every scorecard is in.
    pub ranking: Option<String>,
    /// Seats that were sent the results.
    pub results_sent: HashSet<usize>,
    pub rating: Option<(HashSet<usize>, HashSet<usize>)>,
    pub topic_due: bool,
    pub advance: Option<(String, Option<String>)>,
    pub waiting_for_free: bool,
    pub alone_noticed: bool,
    pub worked_in_topic: bool,
    pub idle_topics: u32,
    pub next_ticket: u64,
    pub internal: mpsc::UnboundedSender<Internal>,
    pub live: Arc<Mutex<Vec<Harness>>>,
    pub flags: Arc<Flags>,
}

/// State a host can read without a round trip.
#[derive(Default)]
pub struct Flags {
    pub ended: AtomicBool,
    pub topics: AtomicBool,
    /// A topic poll is in progress (the engine refuses `advance` then).
    pub polling: AtomicBool,
}
