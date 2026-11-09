//! The Roundtable engine: one task per table, driven by events in the bus's global order.
//!
//! Every rule here traces to `docs/TRACEABILITY.md` (R = README.md, D = the ACP integration
//! design, O = an owner decision):
//! - Turns are sequential in seat order (O: "Agent1 speaks… agent2, 3, 4 all speak…").
//! - An agent is working when ACP reports tool activity during its turn; it is not asked to
//!   announce work (O: "Saying work, thats not a thing"; D §6). The table moves on and its reply,
//!   when it finishes, is its message.
//! - Busy agents are skipped, never cancelled (R §4.4, §10.3).
//! - The floor is offered only while at least two participants are free; a lone free agent is
//!   told once to review the materials, then the table waits (O).
//! - No timers anywhere (O). Failures are loud (O). Nothing polls (O).

use std::collections::{BTreeMap, HashMap, HashSet};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};

use acp_host::events::{AgentState, HarnessExited, HarnessStarted, PromptCompleted, PromptFailed, ToolActivity};
use acp_host::{Harness, PermissionPolicy, ScopePolicy};
use bus::{Bus, Envelope, Tap};
use tokio::sync::mpsc;

use crate::config::{ConfigError, TableConfig, ToolsEndpoint};
use crate::events::*;
use crate::jev::Jev;
use crate::names::genesis_name;
use crate::rules::{Outcome, RoundTracker};

/// The floor is offered only while at least this many participants are free (O).
pub const MIN_FREE_TO_DISCUSS: usize = 2;

/// A command from the chair or a participant tool.
#[derive(Debug, Clone)]
pub enum Command {
    Hold,
    Resume,
    /// Chair guidance: delivered to every participant with the other messages, never judged.
    Guidance(String),
    SetJudging(bool),
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
    pub judging: bool,
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

/// Control surface of a running table. Cheap to clone.
#[derive(Clone)]
pub struct TableHandle {
    pub id: String,
    commands: mpsc::UnboundedSender<Command>,
    tokens: Arc<BTreeMap<String, String>>,
    seats: Arc<Vec<String>>,
    flags: Arc<Flags>,
}

impl TableHandle {
    /// Send a command. False when the table has ended.
    pub fn send(&self, command: Command) -> bool {
        !self.is_ended() && self.commands.send(command).is_ok()
    }
    pub fn is_ended(&self) -> bool {
        self.flags.ended.load(Ordering::SeqCst)
    }
    /// Whether topics are active (they need judging on and a JEV key; O).
    pub fn topics_enabled(&self) -> bool {
        self.flags.topics.load(Ordering::SeqCst)
    }
    /// Whether a topic poll is in progress.
    pub fn polling(&self) -> bool {
        self.flags.polling.load(Ordering::SeqCst)
    }
    /// Seat labels (the chair's), in seat order.
    pub fn seats(&self) -> &[String] {
        &self.seats
    }
    /// Whether `token` is the tools credential issued to `seat` (constant-time compare).
    pub fn seat_token_valid(&self, seat: &str, token: &str) -> bool {
        !self.is_ended() && self.tokens.get(seat).is_some_and(|known| constant_time_eq(known.as_bytes(), token.as_bytes()))
    }
}

fn constant_time_eq(a: &[u8], b: &[u8]) -> bool {
    a.len() == b.len() && a.iter().zip(b).fold(0u8, |acc, (x, y)| acc | (x ^ y)) == 0
}

/// 32 random bytes from the operating system, as hex.
pub fn random_hex() -> String {
    let mut bytes = [0u8; 32];
    getrandom::fill(&mut bytes).expect("the operating system's random source");
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

/// Encode text as one URL path segment.
pub fn path_segment(text: &str) -> String {
    text.bytes()
        .map(|b| match b {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'_' | b'.' => (b as char).to_string(),
            _ => format!("%{b:02X}"),
        })
        .collect()
}

/// Start a table. Returns at once; seat startup and everything after are events. Errors only
/// for an invalid configuration.
pub fn spawn(id: String, cfg: TableConfig, bus: Bus, jev: Jev, tools: Option<ToolsEndpoint>) -> Result<TableHandle, ConfigError> {
    spawn_with(id, cfg, bus, jev, tools, None)
}

/// [`spawn`], with a store of identity profiles for the owner's profile and results messages.
pub fn spawn_with(
    id: String,
    cfg: TableConfig,
    bus: Bus,
    jev: Jev,
    tools: Option<ToolsEndpoint>,
    identities: Option<Arc<dyn crate::config::Identities>>,
) -> Result<TableHandle, ConfigError> {
    cfg.validate()?;
    let (tx, rx) = mpsc::unbounded_channel();
    let (internal_tx, internal_rx) = mpsc::unbounded_channel();
    let tokens: BTreeMap<String, String> = cfg.seats.iter().map(|seat| (seat.name.clone(), random_hex())).collect();
    let flags = Arc::new(Flags::default());
    flags.topics.store(cfg.topics && cfg.judging && jev.configured(), Ordering::SeqCst);
    let handle = TableHandle {
        id: id.clone(),
        commands: tx,
        tokens: Arc::new(tokens.clone()),
        seats: Arc::new(cfg.seats.iter().map(|s| s.name.clone()).collect()),
        flags: flags.clone(),
    };
    let tap = bus.tap();
    let live = Arc::new(Mutex::new(Vec::new()));
    let mut table = Table::new(id.clone(), cfg, bus.clone(), jev, internal_tx, live.clone(), flags.clone());
    table.identities = identities;
    let engine = tokio::spawn(async move {
        table.start(&tokens, tools);
        table.run(rx, internal_rx, tap).await;
    });
    // If the engine task dies, say so loudly and stop the agents instead of hanging.
    tokio::spawn(async move {
        if let Err(error) = engine.await {
            if flags.ended.swap(true, Ordering::SeqCst) {
                return;
            }
            for harness in live.lock().unwrap().iter() {
                harness.shutdown();
            }
            bus.publish(Notice { table: id.clone(), level: "error".into(), text: format!("The engine stopped unexpectedly: {error}") });
            bus.publish(TableEnded { table: id, reason: format!("the engine stopped unexpectedly: {error}") });
        }
    });
    Ok(handle)
}

impl Table {
    fn new(id: String, cfg: TableConfig, bus: Bus, jev: Jev, internal: mpsc::UnboundedSender<Internal>, live: Arc<Mutex<Vec<Harness>>>, flags: Arc<Flags>) -> Self {
        let topic = cfg.topic.clone().filter(|t| !t.trim().is_empty()).unwrap_or_else(|| cfg.objective.clone());
        let seats: Vec<Seat> = cfg
            .seats
            .iter()
            .map(|seat| Seat {
                label: seat.name.clone(),
                name: None,
                harness: None,
                session: String::new(),
                state: SeatState::Starting,
                limit: cfg.base_allowance,
                recovery_due: false,
                activity: Activity::Idle,
                prompt_topic: 1,
                notices: Vec::new(),
                background: false,
                seen_log: 0,
                seen_topic: 0,
                first: true,
                told_to_review: false,
                tools: false,
                monitor: None,
            })
            .collect();
        Self {
            id,
            judging: cfg.judging,
            round_left: seats.len(),
            seats,
            cfg,
            bus,
            jev,
            topics: vec![topic],
            topic_index: 1,
            log: Vec::new(),
            rounds: RoundTracker::default(),
            round_no: 1,
            cursor: 0,
            held: false,
            ended: false,
            floor: None,
            judgements: HashMap::new(),
            polling: None,
            judging_floor: None,
            identities: None,
            session_points: BTreeMap::new(),
            ranking: None,
            results_sent: HashSet::new(),
            rating: None,
            topic_due: false,
            advance: None,
            waiting_for_free: false,
            alone_noticed: false,
            worked_in_topic: false,
            idle_topics: 0,
            next_ticket: 0,
            internal,
            live,
            flags,
        }
    }

    /// Whether the current topic produced an accepted message or file work.
    pub(crate) fn topic_had_input(&self) -> bool {
        let prefix = format!("R{}-", self.topic_index);
        self.worked_in_topic || self.log.iter().any(|e| matches!(e, Entry::Message { id, .. } if id.starts_with(&prefix)))
    }

    /// Topics are a table setting, off by default (owner), and need judging on and a JEV key
    /// (O: "topics require jev").
    // gate: RT-G07 topics are off by default and need JEV
    pub(crate) fn topics_active(&self) -> bool {
        self.cfg.topics && self.judging && self.jev.configured()
    }

    pub(crate) fn topic(&self) -> &str {
        &self.topics[(self.topic_index - 1) as usize]
    }

    pub(crate) fn notice(&self, level: &str, text: impl Into<String>) {
        self.bus.publish(Notice { table: self.id.clone(), level: level.into(), text: text.into() });
    }

    pub(crate) fn ticket(&mut self) -> u64 {
        self.next_ticket += 1;
        self.next_ticket
    }

    /// The limit for this seat's next discussion prompt: the recovery limit once after it was
    /// skipped while busy, otherwise the table's reply limit (owner's spec).
    pub(crate) fn limit_for(&self, i: usize) -> Option<usize> {
        let base = self.cfg.base_allowance?;
        Some(if self.seats[i].recovery_due { self.cfg.recovery_allowance } else { base })
    }

    fn start(&mut self, tokens: &BTreeMap<String, String>, tools: Option<ToolsEndpoint>) {
        let _ = std::fs::create_dir_all(&self.cfg.workspace);
        let workspace = self.cfg.workspace.canonicalize().unwrap_or_else(|_| self.cfg.workspace.clone());
        self.cfg.workspace = workspace.clone();
        let scope = self.cfg.scope.clone().unwrap_or_else(|| workspace.clone());
        let policy: Arc<dyn PermissionPolicy> = Arc::new(ScopePolicy::new(scope));
        self.bus.publish(TableOpened {
            table: self.id.clone(),
            objective: self.cfg.objective.clone(),
            topic: self.topic().to_string(),
            workspace: workspace.display().to_string(),
            seats: self.cfg.seats.iter().map(|s| SeatInfo { name: s.name.clone(), harness: s.harness.clone(), settings: s.settings.iter().cloned().collect() }).collect(),
            judging: self.judging,
            jev_configured: self.jev.configured(),
            base_allowance: self.cfg.base_allowance,
            recovery_allowance: self.cfg.recovery_allowance,
            rounds: self.cfg.rounds,
        });
        if self.judging && !self.jev.configured() {
            self.notice("warn", "Judging is on but no OpenRouter key is set: contributions are shared unjudged until a key is provided.");
        }
        for (index, seat) in self.cfg.seats.iter().cloned().enumerate() {
            let bus = self.bus.clone();
            let policy = policy.clone();
            let workspace = workspace.clone();
            let harness_id = format!("{}/{}", self.id, seat.name);
            let tools = tools.as_ref().map(|t| {
                let url = format!("{}/{}/{}", t.base_url.trim_end_matches('/'), path_segment(&self.id), path_segment(&seat.name));
                (url, tokens[&seat.name].clone())
            });
            let key = self.jev.key().map(str::to_string);
            let internal = self.internal.clone();
            let live = self.live.clone();
            tokio::spawn(async move {
                let mut warnings = Vec::new();
                let result = start_seat(&seat, harness_id, bus, policy, &workspace, tools, key, &live, &mut warnings).await;
                let _ = internal.send(Internal::SeatStarted { index, result, warnings });
            });
        }
    }

    async fn run(&mut self, mut commands: mpsc::UnboundedReceiver<Command>, mut internal: mpsc::UnboundedReceiver<Internal>, mut tap: Tap) {
        while !self.ended {
            self.step();
            self.flags.polling.store(self.polling.is_some(), Ordering::SeqCst);
            tokio::select! {
                command = commands.recv() => match command {
                    Some(command) => self.command(command),
                    // not a gate: nobody can control the table any more
                    None => self.end("every handle was dropped"),
                },
                Some(message) = internal.recv() => self.internal(message),
                Some(envelope) = tap.recv() => self.on_bus(&envelope),
            }
        }
    }

    fn on_bus(&mut self, envelope: &Envelope) {
        if let Some(event) = envelope.downcast::<PromptCompleted>() {
            self.on_completed(event);
        } else if let Some(event) = envelope.downcast::<ToolActivity>() {
            self.on_tool(event);
        } else if let Some(event) = envelope.downcast::<PromptFailed>() {
            self.on_failed(event);
        } else if let Some(event) = envelope.downcast::<HarnessExited>() {
            self.on_exited(event);
        } else if let Some(event) = envelope.downcast::<HarnessStarted>() {
            self.on_started(event);
        } else if let Some(event) = envelope.downcast::<AgentState>() {
            // Only a report changes what is known: `None` means not reported.
            if let (Some(i), Some(count)) = (self.seat_of(&event.harness), event.background) {
                let working = count > 0;
                if self.seats[i].background != working {
                    self.seats[i].background = working;
                    self.bus.publish(BackgroundWork { table: self.id.clone(), seat: self.seats[i].label.clone(), items: count });
                    if !working {
                        self.waiting_for_free = false;
                    }
                }
            }
        } else if let Some(event) = envelope.downcast::<agent_monitor::MonitorUnavailable>() {
            // Every monitoring failure, at attach or later (a capture that could not start or
            // stopped), is shown independently of the agent's own reports (R §10.2, F09).
            if let Some(i) = event.harness.id.as_deref().and_then(|id| self.seat_of(id)) {
                self.notice("error", format!("AgentSight cannot observe {}: {event}", self.seats[i].label));
            }
        }
    }

    pub(crate) fn seat_of(&self, harness: &str) -> Option<usize> {
        let label = harness.strip_prefix(&self.id)?.strip_prefix('/')?;
        self.seats.iter().position(|seat| seat.label == label)
    }

    /// Move the table forward as far as it can without waiting.
    fn step(&mut self) {
        // The discussion starts once the table is seated, so turns run in seat order from the
        // first participant (O: "Agent1 speaks… agent2, 3, 4…"). Commands still work meanwhile.
        let seating = self.seats.iter().any(|s| s.state == SeatState::Starting);
        if self.held || self.ended || self.rating.is_some() || seating || !self.seats.iter().any(|s| s.state == SeatState::Ready) {
            return;
        }
        if let Some(polling) = &self.polling {
            // gate: RT-G21 a topic poll waits for every agent
            if polling.scoring.is_none() && polling.waiting.is_empty() && polling.pending.is_empty() {
                self.finish_polling();
            }
            return;
        }
        // gate: RT-G10 the next turn waits for JEV's verdict
        if self.floor.is_some() || self.judging_floor.is_some() {
            return;
        }
        if let Some((by, topic)) = self.advance.take().filter(|_| self.topics_active()) {
            match topic {
                Some(topic) => self.change_topic(topic, format!("set by {by}"), Vec::new()),
                None => self.topic_due = true,
            }
        }
        if self.topic_due && self.topics_active() {
            self.start_polling();
            return;
        }
        self.topic_due = false;
        if self.waiting_for_free {
            return;
        }
        self.give_floor();
    }

    /// Ready, with no prompt in progress and no background work reported.
    fn free_to_speak(&self, i: usize) -> bool {
        let seat = &self.seats[i];
        seat.state == SeatState::Ready && seat.activity == Activity::Idle && !seat.background
    }

    fn give_floor(&mut self) {
        let free: Vec<usize> = (0..self.seats.len()).filter(|&i| self.free_to_speak(i)).collect();
        let ready = self.seats.iter().filter(|s| s.state == SeatState::Ready).count();
        // gate: RT-G03 the table waits until two agents are free
        if free.len() < MIN_FREE_TO_DISCUSS {
            if let [lone] = free[..] {
                if ready > 1 && !self.seats[lone].told_to_review {
                    self.ask_to_review(lone);
                } else if ready == 1 && !self.seats.iter().any(|s| s.state == SeatState::Starting) && !self.alone_noticed {
                    self.alone_noticed = true;
                    self.notice("error", format!("Only {} is left at the table; a discussion needs at least two participants.", self.seats[lone].label));
                }
            }
            // gate: RT-G03 fewer than two agents are free: the table waits
            self.waiting_for_free = true;
            return;
        }
        for &i in &free {
            self.seats[i].told_to_review = false;
        }
        let n = self.seats.len();
        for _ in 0..n {
            let i = self.cursor;
            self.cursor = (i + 1) % n;
            if self.seats[i].state != SeatState::Ready {
                self.opportunity(None);
                continue;
            }
            if self.free_to_speak(i) {
                if self.offer(i, None, Activity::Floor) {
                    return;
                }
                self.opportunity(Some(Outcome::Failed));
            } else {
                // gate: RT-G04 a busy agent's turn is skipped
                // Skipped while busy: its next discussion prompt gets the recovery limit once.
                self.seats[i].recovery_due = true;
                self.bus.publish(Skipped { table: self.id.clone(), seat: self.seats[i].label.clone(), reason: "working".into() });
                self.opportunity(Some(Outcome::SkippedWorking));
            }
            if self.topic_due {
                return;
            }
        }
        // gate: RT-G03 nobody free to take the turn: the table waits
        self.waiting_for_free = true;
    }

    fn ask_to_review(&mut self, i: usize) {
        self.seats[i].told_to_review = true;
        // Its reply is a contribution, so the owner's final allowance line still applies (F13).
        if self.offer(i, Some(crate::prompts::REVIEW.to_string()), Activity::Reviewing) {
            self.bus.publish(ReviewAsked { table: self.id.clone(), seat: self.seats[i].label.clone() });
        }
    }

    /// Send seat `i` a prompt: its turn (`ask` None) or a special request. False on failure.
    pub(crate) fn offer(&mut self, i: usize, ask: Option<String>, activity: fn(u64) -> Activity) -> bool {
        let discussion = matches!(activity(0), Activity::Floor(_) | Activity::Reviewing(_));
        let limit = self.limit_for(i);
        let (text, commit) = self.turn_prompt(i, ask, discussion);
        let harness = self.seats[i].harness.clone().expect("a ready seat has a harness");
        match harness.prompt(&self.seats[i].session, text) {
            Ok(prompt) => {
                self.commit(i, commit);
                let seat = &mut self.seats[i];
                if discussion {
                    seat.limit = limit;
                    seat.recovery_due = false;
                }
                seat.activity = activity(prompt);
                seat.prompt_topic = self.topic_index;
                if matches!(seat.activity, Activity::Floor(_)) {
                    self.floor = Some((i, prompt));
                    self.bus.publish(FloorGiven { table: self.id.clone(), seat: seat.label.clone(), round: self.round_no, allowance: seat.limit });
                }
                true
            }
            Err(error) => {
                let text = format!("{}: the prompt could not be sent: {error:#}", self.seats[i].label);
                self.bus.publish(TurnFailed { table: self.id.clone(), seat: self.seats[i].label.clone(), error: format!("{error:#}") });
                self.notice("error", text);
                false
            }
        }
    }

    /// Count one opportunity; after every seat has had one, close the round.
    pub(crate) fn opportunity(&mut self, outcome: Option<Outcome>) {
        if let Some(outcome) = outcome {
            self.rounds.record(outcome);
        }
        self.round_left = self.round_left.saturating_sub(1);
        if self.round_left == 0 {
            self.round_left = self.seats.len();
            let advance = self.rounds.close_round();
            self.bus.publish(RoundClosed { table: self.id.clone(), round: self.round_no, topic_may_advance: advance && self.topics_active() });
            // gate: RT-G05 the table ends after its rounds
            // The table ends after its last round (owner: 10 by default), with the rating round.
            if self.cfg.rounds == Some(self.round_no) {
                self.notice("info", format!("The table finished its {} rounds.", self.round_no));
                // gate: RT-G05 the last round is done: the rating round starts
                self.start_rating();
                return;
            }
            self.round_no += 1;
            // gate: RT-G06 a table with no round limit ends when there is no more good input
            // No round limit: the table ends when there is no more good input. Two rounds with
            // nothing accepted end it without JEV (no topics), or with JEV when the current topic
            // produced no accepted message and no file work at all.
            if advance && self.cfg.rounds.is_none() && (!self.topics_active() || !self.topic_had_input()) {
                self.notice("info", "The table ended: two rounds in a row brought no accepted message.");
                // gate: RT-G06 no more good input: the rating round starts
                self.start_rating();
                return;
            }
            // gate: RT-G08 two quiet rounds start a topic poll
            if advance && self.topics_active() {
                self.topic_due = true;
            }
        }
    }

    fn release_floor(&mut self, i: usize, prompt: u64) {
        if self.floor == Some((i, prompt)) {
            self.floor = None;
        }
    }

    /// ACP tool activity during a turn: the agent is working (D §6). The table moves on.
    fn on_tool(&mut self, event: &ToolActivity) {
        let Some(i) = self.seat_of(&event.harness) else { return };
        match self.seats[i].activity {
            Activity::Floor(prompt) if event.prompt == Some(prompt) => {
                self.seats[i].activity = Activity::Working(prompt);
                self.worked_in_topic = true;
                self.release_floor(i, prompt);
                self.bus.publish(WorkStarted { table: self.id.clone(), seat: self.seats[i].label.clone() });
                self.opportunity(Some(Outcome::SkippedWorking));
            }
            // A proposer that uses tools is still answering the poll; its reply when it finishes
            // is its proposal, and the poll waits for it (R §7).
            _ => {}
        }
    }

    fn on_completed(&mut self, event: &PromptCompleted) {
        let Some(i) = self.seat_of(&event.harness) else { return };
        if self.seats[i].activity.prompt() != Some(event.prompt) {
            return;
        }
        let activity = self.seats[i].activity;
        self.seats[i].activity = Activity::Idle;
        self.waiting_for_free = false;
        // gate: RT-G09 only the text after the last tool call becomes the message
        // The agent's message is what it says once it has finished: the turn's final message,
        // not its narration before tool calls. Builder decision from an observed failure: round
        // 3 submitted whole turn transcripts, and JEV vetoed the narration. Open with the owner
        // (audit Q4).
        match activity {
            Activity::Floor(prompt) => {
                self.release_floor(i, prompt);
                if let Some(outcome) = self.resolve_reply(i, &event.final_message, false) {
                    self.opportunity(Some(outcome));
                }
            }
            Activity::Working(_) | Activity::Reviewing(_) => {
                self.resolve_reply(i, &event.final_message, true);
            }
            Activity::Proposing(_) => self.on_proposal(i, &event.final_message),
            Activity::Rating(_) => self.on_rating(i, &event.final_message),
            Activity::Notified(_) | Activity::Idle => {}
        }
        self.settle_rating(i);
        self.settle_results(i);
        self.settle_poll(i);
    }

    /// During the rating round, a seat that owes ratings and whose prompt just ended: asked
    /// now if it is free and was not asked yet (it was busy at End), or no longer owed if it
    /// is gone. Called on every way a prompt ends, so the round cannot be stranded.
    fn settle_rating(&mut self, i: usize) {
        let Some((left, asked)) = self.rating.as_ref() else { return };
        if !left.contains(&i) {
            return;
        }
        if self.seats[i].state != SeatState::Ready {
            self.rating_done(i);
        } else if !asked.contains(&i) && self.seats[i].activity == Activity::Idle {
            self.ask_to_rate(i);
        }
    }

    fn on_failed(&mut self, event: &PromptFailed) {
        let Some(i) = self.seat_of(&event.harness) else { return };
        if self.seats[i].activity.prompt() != Some(event.prompt) {
            return;
        }
        let activity = self.seats[i].activity;
        self.seats[i].activity = Activity::Idle;
        self.waiting_for_free = false;
        let label = self.seats[i].label.clone();
        self.bus.publish(TurnFailed { table: self.id.clone(), seat: label.clone(), error: event.error.clone() });
        self.notice("error", format!("{label}'s turn failed: {}", event.error));
        match activity {
            Activity::Floor(prompt) => {
                self.release_floor(i, prompt);
                self.opportunity(Some(Outcome::Failed));
            }
            Activity::Proposing(_) => {
                if let Some(p) = self.polling.as_mut() {
                    p.waiting.remove(&i);
                }
            }
            Activity::Rating(_) => self.rating_done(i),
            _ => {}
        }
        self.settle_rating(i);
        self.settle_results(i);
        self.settle_poll(i);
    }

    /// A harness process ended: a bug, so loud (owner, 2026-11-06: "if theree is a bug we fail loudly and fix it").
    fn on_exited(&mut self, event: &HarnessExited) {
        let Some(i) = self.seat_of(&event.harness) else { return };
        if matches!(self.seats[i].state, SeatState::Gone | SeatState::Failed) || self.ended {
            return;
        }
        let activity = self.seats[i].activity;
        self.seats[i].state = SeatState::Gone;
        self.seats[i].activity = Activity::Idle;
        self.waiting_for_free = false;
        let label = self.seats[i].label.clone();
        let detail = format!("harness exited (code {:?}). Last output: {}", event.code, event.stderr_tail.lines().rev().take(5).collect::<Vec<_>>().into_iter().rev().collect::<Vec<_>>().join(" | "));
        self.notice("error", format!("{label} crashed: {detail}"));
        self.bus.publish(SeatGone { table: self.id.clone(), seat: label, detail });
        match activity {
            Activity::Floor(prompt) => {
                self.release_floor(i, prompt);
                self.opportunity(Some(Outcome::Failed));
            }
            Activity::Proposing(_) => {
                if let Some(p) = self.polling.as_mut() {
                    p.waiting.remove(&i);
                }
            }
            Activity::Rating(_) => self.rating_done(i),
            _ => {}
        }
        self.settle_rating(i);
        self.settle_results(i);
        self.settle_poll(i);
        if !self.seats.iter().any(|s| matches!(s.state, SeatState::Starting | SeatState::Ready)) {
            // not a gate: no participant is left to run
            self.end("no participants left");
        }
    }

    /// Attach AgentSight to a harness process as soon as it exists (R §10.2; D §8 correlation by pid).
    fn on_started(&mut self, event: &HarnessStarted) {
        let (Some(index), Some(pid)) = (self.seat_of(&event.harness), event.pid) else { return };
        let bus = self.bus.clone();
        let internal = self.internal.clone();
        let id = event.harness.clone();
        tokio::spawn(async move {
            let result = agent_monitor::Monitor::attach(&bus, agent_monitor::Harness { pid, id: Some(id) }).await.map_err(|e| e.reason);
            let _ = internal.send(Internal::Monitor { index, result });
        });
    }

    fn internal(&mut self, message: Internal) {
        match message {
            // A failure needs nothing here: attach publishes it as `monitor.unavailable`, which
            // on_bus turns into the loud notice.
            Internal::Monitor { index, result } => {
                if let Ok(monitor) = result {
                    self.seats[index].monitor = Some(monitor);
                }
            }
            Internal::SeatStarted { index, result, warnings } => {
                for warning in warnings {
                    self.notice("error", format!("{}: {warning}", self.seats[index].label));
                }
                match result {
                    Ok((harness, session, tools, protocol)) if !self.ended => {
                        let name = genesis_name(&session);
                        let seat = &mut self.seats[index];
                        seat.harness = Some(harness);
                        seat.session = session.clone();
                        seat.name = Some(name.clone());
                        seat.tools = tools;
                        seat.state = SeatState::Ready;
                        self.waiting_for_free = false;
                        self.alone_noticed = false;
                        self.bus.publish(SeatReady { table: self.id.clone(), seat: seat.label.clone(), name, session, tools, protocol });
                    }
                    Ok((harness, _, _, _)) => harness.shutdown(),
                    Err(error) => {
                        self.seats[index].state = SeatState::Failed;
                        self.notice("error", format!("{} could not start: {error}", self.seats[index].label));
                        self.bus.publish(SeatFailed { table: self.id.clone(), seat: self.seats[index].label.clone(), error });
                        if !self.seats.iter().any(|s| matches!(s.state, SeatState::Starting | SeatState::Ready)) {
                            // not a gate: no participant could start
                            self.end("no participant could start");
                        }
                    }
                }
            }
            Internal::Judged { ticket, result } => self.on_judged(ticket, result),
            Internal::Scored { ticket, result } => self.on_scored(ticket, result),
        }
    }

    fn command(&mut self, command: Command) {
        match command {
            Command::Hold => {
                self.held = true;
                self.bus.publish(Held { table: self.id.clone(), held: true });
            }
            Command::Resume => {
                self.held = false;
                self.bus.publish(Held { table: self.id.clone(), held: false });
            }
            Command::Guidance(text) => {
                self.log.push(Entry::Chair { text: text.clone(), round: self.round_no });
                self.bus.publish(ChairSpoke { table: self.id.clone(), text });
            }
            Command::SetJudging(on) => {
                self.judging = on;
                self.settings_changed();
            }
            Command::SetJevKey(key) => {
                self.jev.set_key(key);
                self.settings_changed();
            }
            // gate: RT-G11 advance is refused during a poll and applied when the floor is free
            Command::Advance { by, topic } => {
                if !self.topics_active() {
                    self.notice("error", format!("{by} asked to advance the topic, but topics need JEV (judging on and a key)."));
                } else if self.polling.is_some() {
                    self.notice("error", format!("{by} asked to advance the topic during a topic poll; the poll decides."));
                } else {
                    self.advance = Some((by, topic.filter(|t| !t.trim().is_empty())));
                }
            }
            Command::Feedback { from, to, ratings, note } => {
                // gate: RT-G15 feedback must name exactly one participant
                // Feedback goes to an identity, so it must name exactly one other participant
                // (F11). The sender hears at its next turn when it did not.
                let Some(i) = self.seats.iter().position(|s| s.label == from) else { return };
                let targets: Vec<usize> = (0..self.seats.len()).filter(|&j| j != i && self.seats[j].name.as_deref() == Some(to.as_str())).collect();
                if targets.len() != 1 {
                    // gate: RT-G15 feedback must name exactly one other participant
                    let why = format!("Your feedback for {to:?} was not recorded: it matches {} other participants.", targets.len());
                    self.notice("error", format!("{from}: {why}"));
                    self.seats[i].notices.push(why);
                    return;
                }
                let from_name = self.seats[i].name.clone().unwrap_or_else(|| from.clone());
                let to_label = self.seats[targets[0]].label.clone();
                let to_session = self.seats[targets[0]].session.clone();
                self.bus.publish(FeedbackGiven { table: self.id.clone(), from, from_name, to: to_label, to_name: to, to_session, ratings, note });
            }
            // not a gate: the chair ends the table
            Command::End => {
                if self.rating.is_some() {
                    self.end("ended by the chair during the rating round");
                } else {
                    // not a gate: the chair's End starts the rating round
                    self.start_rating();
                }
            }
        }
    }

    fn settings_changed(&mut self) {
        // Topics require JEV (O). Losing it stops topic work in progress: a poll still
        // collecting or scoring, and an advance not yet applied.
        if !self.topics_active() {
            if self.polling.take().is_some() {
                self.notice("info", "Topic selection stopped: topics need judging on and a key. The current topic continues.");
                self.rounds.reset();
                self.round_left = self.seats.len();
            }
            if let Some((by, _)) = self.advance.take() {
                self.notice("info", format!("{by}'s topic advance was dropped: topics need judging on and a key."));
            }
            self.topic_due = false;
        }
        self.flags.topics.store(self.topics_active(), Ordering::SeqCst);
        self.bus.publish(SettingsChanged { table: self.id.clone(), judging: self.judging, jev_configured: self.jev.configured() });
    }

    pub(crate) fn end(&mut self, reason: &str) {
        if self.ended {
            return;
        }
        self.ended = true;
        self.flags.ended.store(true, Ordering::SeqCst);
        for harness in self.live.lock().unwrap().iter() {
            harness.shutdown();
        }
        self.bus.publish(TableEnded { table: self.id.clone(), reason: reason.into() });
    }

    pub(crate) fn names(&self) -> Vec<String> {
        self.seats.iter().filter_map(|s| s.name.clone()).collect()
    }
}

/// Launch one seat's harness, open its session and apply its settings.
#[allow(clippy::too_many_arguments)]
async fn start_seat(
    seat: &crate::config::SeatConfig,
    harness_id: String,
    bus: Bus,
    policy: Arc<dyn PermissionPolicy>,
    workspace: &std::path::Path,
    tools: Option<(String, String)>,
    key: Option<String>,
    live: &Mutex<Vec<Harness>>,
    warnings: &mut Vec<String>,
) -> Result<(Harness, String, bool, u16), String> {
    let (launch, warning) = seat.launch_spec(key);
    warnings.extend(warning);
    let harness = Harness::launch(harness_id, seat.harness.clone(), &launch, bus, policy).await.map_err(|e| format!("{e:#}"))?;
    live.lock().unwrap().push(harness.clone());
    let protocol = harness.protocol_version();
    let mut servers = Vec::new();
    let offered = tools.is_some() && harness.accepts_http_mcp();
    if let (Some((url, token)), true) = (&tools, offered) {
        servers.push(acp_host::acp_schema::McpServer::Http(
            acp_host::acp_schema::McpServerHttp::new("roundtable", url.clone())
                .headers(vec![acp_host::acp_schema::HttpHeader::new("Authorization", format!("Bearer {token}"))]),
        ));
    }
    if tools.is_some() && !offered {
        warnings.push("its harness does not accept HTTP MCP servers, so it has no Roundtable tools".into());
    }
    let opened = match &seat.resume_session {
        Some(id) => harness.resume_session(workspace, id, servers).await,
        None => harness.open_session(workspace, servers).await,
    };
    let session = match opened {
        Ok(session) => session,
        Err(error) => {
            harness.shutdown();
            return Err(format!("{error:#}"));
        }
    };
    for (key, value) in &seat.settings {
        if let Err(error) = harness.set_config(&session, key, value).await {
            warnings.push(format!("could not set {key} to {value}: {error:#}"));
        }
    }
    let routed_by_env = crate::config::PERMISSION_ROUTING_ENV.iter().any(|name| seat.launch.env.contains_key(*name));
    if !seat.settings.iter().any(|(k, _)| k == "mode") && !routed_by_env {
        warnings.push("no mode is set that routes permission requests to Roundtable or selects a sandbox; the workspace scope may not be enforced for this harness".into());
    }
    Ok((harness, session, offered, protocol))
}
