//! The Roundtable engine: one task per table, driven by events in the bus's global order.
//!
//! Every rule here traces to `context/roundtable-original-2026-11-05/docs/TRACEABILITY.md`
//! from the repository root (R = README.md, D = the ACP integration design, O = an owner
//! decision):
//! - Turns are sequential in seat order (O: "Agent1 speaks… agent2, 3, 4 all speak…").
//! - An agent is working when ACP reports tool activity during its turn; it is not asked to
//!   announce work (O: "Saying work, thats not a thing"; D §6). The table moves on and its reply,
//!   when it finishes, is its message.
//! - Busy agents are skipped, never cancelled (R §4.4, §10.3).
//! - The floor is offered only while at least two participants are free; a lone free agent is
//!   told once to review the materials, then the table waits (O).
//! - No timers anywhere (O). Failures are loud (O). Nothing polls (O).

use std::collections::{BTreeMap, HashMap, HashSet};
use std::sync::atomic::Ordering;
use std::sync::{Arc, Mutex};

use acp_host::events::{AgentState, HarnessExited, HarnessStarted, PromptCompleted, PromptFailed, ToolActivity};
use acp_host::{Harness, PermissionPolicy, ScopePolicy};
use bus::{Bus, Envelope, Tap};
use tokio::sync::mpsc;

use crate::config::{TableConfig, ToolsEndpoint};
use crate::events::*;
use crate::jev::Jev;
use crate::rules::{Outcome, RoundTracker};

use crate::table::*;
use crate::agents::start_seat;
use crate::handle::path_segment;

impl Table {
    pub(crate) fn new(id: String, cfg: TableConfig, bus: Bus, jev: Jev, internal: mpsc::UnboundedSender<Internal>, live: Arc<Mutex<Vec<Harness>>>, flags: Arc<Flags>) -> Self {
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

    /// Topics are a table setting, off by default (owner). JEV is required (owner), so a
    /// table only lacks it when the chair removes the key; topics stop then.
    // gate: RT-G07 topics are off by default and need JEV
    pub(crate) fn topics_active(&self) -> bool {
        self.cfg.topics && self.jev.configured()
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

    pub(crate) fn start(&mut self, tokens: &BTreeMap<String, String>, tools: Option<ToolsEndpoint>) {
        let _ = std::fs::create_dir_all(&self.cfg.workspace);
        let workspace = self.cfg.workspace.canonicalize().unwrap_or_else(|_| self.cfg.workspace.clone());
        self.cfg.workspace = workspace.clone();
        let scope = self.cfg.scope.clone().unwrap_or_else(|| workspace.clone());
        let policy: Arc<dyn PermissionPolicy> = Arc::new(ScopePolicy::with_rules(scope, self.cfg.permissions.clone()));
        self.bus.publish(TableOpened {
            table: self.id.clone(),
            objective: self.cfg.objective.clone(),
            topic: self.topic().to_string(),
            workspace: workspace.display().to_string(),
            seats: self.cfg.seats.iter().map(|s| SeatInfo { name: s.name.clone(), harness: s.harness.clone(), settings: s.settings.iter().cloned().collect() }).collect(),
            jev_configured: self.jev.configured(),
            base_allowance: self.cfg.base_allowance,
            recovery_allowance: self.cfg.recovery_allowance,
            rounds: self.cfg.rounds,
        });
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
            let force_stop = self.cfg.force_stop;
            tokio::spawn(async move {
                let mut warnings = Vec::new();
                let result = start_seat(&seat, harness_id, bus, policy, &workspace, tools, key, force_stop, &live, &mut warnings).await;
                let _ = internal.send(Internal::SeatStarted { index, result, warnings });
            });
        }
    }

    pub(crate) async fn run(&mut self, mut commands: mpsc::UnboundedReceiver<Command>, mut internal: mpsc::UnboundedReceiver<Internal>, mut tap: Tap) {
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

    pub(crate) fn on_bus(&mut self, envelope: &Envelope) {
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
    pub(crate) fn step(&mut self) {
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
    pub(crate) fn free_to_speak(&self, i: usize) -> bool {
        let seat = &self.seats[i];
        seat.state == SeatState::Ready && seat.activity == Activity::Idle && !seat.background
    }

    pub(crate) fn give_floor(&mut self) {
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

    pub(crate) fn ask_to_review(&mut self, i: usize) {
        self.seats[i].told_to_review = true;
        // Its reply is a contribution.
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
            let advance = self.rounds.close_round_after(self.cfg.quiet_rounds);
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
            // No round limit: the table ends when there is no more good input. `table.quiet_rounds`
            // rounds in a row with nothing accepted end it when topics are off, or, with topics on,
            // when the current topic produced no accepted message and no file work at all.
            if advance && self.cfg.rounds.is_none() && (!self.topics_active() || !self.topic_had_input()) {
                self.notice("info", format!("The table ended: {} rounds in a row brought no accepted message.", self.cfg.quiet_rounds));
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

    pub(crate) fn release_floor(&mut self, i: usize, prompt: u64) {
        if self.floor == Some((i, prompt)) {
            self.floor = None;
        }
    }

}
