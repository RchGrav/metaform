//! How the table reacts to agents, JEV and the chair: ACP events, judgements, commands, and
//! the end of the table.

use std::sync::atomic::Ordering;
use std::sync::{Arc, Mutex};

use acp_host::events::{HarnessExited, HarnessStarted, PromptCompleted, PromptFailed, ToolActivity};
use acp_host::{Harness, PermissionPolicy};
use bus::Bus;

use crate::events::*;
use crate::names::genesis_name;
use crate::rules::Outcome;

use crate::table::*;

impl Table {
    pub(crate) fn on_tool(&mut self, event: &ToolActivity) {
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

    pub(crate) fn on_completed(&mut self, event: &PromptCompleted) {
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
    pub(crate) fn settle_rating(&mut self, i: usize) {
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

    pub(crate) fn on_failed(&mut self, event: &PromptFailed) {
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
    pub(crate) fn on_exited(&mut self, event: &HarnessExited) {
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
        self.notice("error", format!("{label} left the table unexpectedly: {detail}"));
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
    pub(crate) fn on_started(&mut self, event: &HarnessStarted) {
        let (Some(index), Some(pid)) = (self.seat_of(&event.harness), event.pid) else { return };
        let bus = self.bus.clone();
        let internal = self.internal.clone();
        let id = event.harness.clone();
        tokio::spawn(async move {
            let result = agent_monitor::Monitor::attach(&bus, agent_monitor::Harness { pid, id: Some(id) }).await.map_err(|e| e.reason);
            let _ = internal.send(Internal::Monitor { index, result });
        });
    }

    pub(crate) fn internal(&mut self, message: Internal) {
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

    pub(crate) fn command(&mut self, command: Command) {
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
            Command::SetJevKey(key) => {
                self.jev.set_key(key);
                self.settings_changed();
            }
            // gate: RT-G11 advance is refused during a poll and applied when the floor is free
            Command::Advance { by, topic } => {
                if !self.topics_active() {
                    self.notice("error", format!("{by} asked to advance the topic, but topics are off or JEV has no key."));
                } else if self.polling.is_some() && self.cfg.hold_advance_during_poll {
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

    pub(crate) fn settings_changed(&mut self) {
        // Topics need JEV's key. Losing it stops topic work in progress: a poll still
        // collecting or scoring, and an advance not yet applied.
        if !self.topics_active() {
            if self.polling.take().is_some() {
                self.notice("info", "Topic selection stopped: JEV has no key. The current topic continues.");
                self.rounds.reset();
                self.round_left = self.seats.len();
            }
            if let Some((by, _)) = self.advance.take() {
                self.notice("info", format!("{by}'s topic advance was dropped: JEV has no key."));
            }
            self.topic_due = false;
        }
        self.flags.topics.store(self.topics_active(), Ordering::SeqCst);
        self.bus.publish(SettingsChanged { table: self.id.clone(), jev_configured: self.jev.configured() });
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
pub(crate) async fn start_seat(
    seat: &crate::config::SeatConfig,
    harness_id: String,
    bus: Bus,
    policy: Arc<dyn PermissionPolicy>,
    workspace: &std::path::Path,
    tools: Option<(String, String)>,
    key: Option<String>,
    force_stop: bool,
    live: &Mutex<Vec<Harness>>,
    warnings: &mut Vec<String>,
) -> Result<(Harness, String, bool, u16), String> {
    let (mut launch, warning) = seat.launch_spec(key);
    launch.force_stop = force_stop;
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
