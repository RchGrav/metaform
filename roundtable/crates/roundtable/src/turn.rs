//! Inside an opportunity: the prompt a seat receives (O format), how its reply is resolved,
//! judging (the owner's rule is that judging never holds the table, R §4; today the next turn
//! waits for JEV's verdict, gate RT-G10, owner disposition pending), the next-topic poll (only
//! with JEV, O), and
//! the rating round at the end (O).

use std::collections::BTreeMap;

use crate::table::{Entry, Internal, Judgement, Table};
use crate::events::*;
use crate::jev;
use crate::prompts;
use crate::rules::{self, Outcome, Reply, SCORE_PASS};

/// What a prompt consumed; applied only once the prompt was actually sent.
pub(crate) struct Commit {
    log: usize,
    topic: u64,
    /// The notices went out with this prompt.
    notices: bool,
}

impl Table {
    /// The prompt for seat `i`, in the owner's order: the round line, the notices (length,
    /// rejection, not evaluated), each other participant's message, then `ask` when given (O).
    /// Only what is new since its last turn; its ACP session keeps the rest. `ask` is appended
    /// for special requests (review, topic proposal, ratings). `discussion`: a
    /// floor turn or a review, whose reply is a contribution. The round line and the notices go
    /// only to such a turn, as R §4.6 says "when the vetoed participant's next turn arrives".
    /// On its first turn the agent gets the owner's roundtable prompt, with this turn in place of
    /// `{{delivery_json}}` and the owner's participant prompt in place of
    /// `{{custom_roundtable_prompt}}`.
    pub(crate) fn turn_prompt(&self, i: usize, ask: Option<String>, discussion: bool) -> (String, Commit) {
        let seat = &self.seats[i];
        let mut parts: Vec<String> = Vec::new();
        if discussion {
            parts.push(rules::round_label(self.round_no, self.cfg.rounds));
        }
        if seat.first {
            // A returning identity hears its standing (owner's `session_profile`).
            if let (Some(store), Some(name)) = (self.identities.as_ref(), seat.name.as_deref()) {
                match store.profile(&seat.session) {
                    Ok(Some(profile)) if profile.ratings > 0 => parts.push(
                        prompts::SESSION_PROFILE
                            .replacen("<score/>", &prompts::points(profile.score), 1)
                            .replacen("<ratings/>", &profile.ratings.to_string(), 1)
                            .replacen("<sessions/>", &profile.sessions.to_string(), 1),
                    ),
                    Ok(_) => {}
                    Err(error) => self.notice("error", format!("{name}'s identity profile could not be read: {error}")),
                }
            }
        }
        if discussion {
            // gate: RT-G16 rejection reasons wait for the next discussion turn
            parts.extend(seat.notices.iter().cloned());
        }
        // The first turn's roundtable prompt already names the topic.
        if self.topics_active() && !seat.first && seat.seen_topic != self.topic_index {
            parts.push(format!("Current topic: {}", self.topic()));
        }
        for entry in &self.log[seat.seen_log.min(self.log.len())..] {
            match entry {
                Entry::Message { id, seat: author, name, text, .. } if author != &seat.label => parts.push(format!("[{id}] {name}: {text}")),
                Entry::Chair { text, .. } => parts.push(format!("Chair: {text}")),
                _ => {}
            }
        }
        parts.extend(ask);
        let delivery = parts.join("\n\n");
        let text = if seat.first {
            let custom = prompts::participant_prompt(&self.cfg.objective);
            let workspace = self.cfg.workspace.display().to_string();
            prompts::roundtable_prompt(&prompts::Fill {
                agent_name: seat.name.as_deref().unwrap_or(&seat.label),
                topic: self.topic(),
                custom: &custom,
                workspace: &workspace,
                delivery: &delivery,
            })
        } else {
            delivery
        };
        (text, Commit { log: self.log.len(), topic: self.topic_index, notices: discussion })
    }

    pub(crate) fn commit(&mut self, i: usize, commit: Commit) {
        let seat = &mut self.seats[i];
        seat.first = false;
        if commit.notices {
            seat.notices.clear();
        }
        seat.seen_log = commit.log;
        seat.seen_topic = commit.topic;
    }

    /// Resolve a reply. `after_work`: it came after the agent worked (its opportunity was
    /// already counted). Returns the floor outcome for a floor reply.
    pub(crate) fn resolve_reply(&mut self, i: usize, reply: &str, after_work: bool) -> Option<Outcome> {
        let label = self.seats[i].label.clone();
        let outcome = match rules::classify(reply) {
            Reply::Pass => {
                self.bus.publish(Passed { table: self.id.clone(), seat: label });
                Outcome::Passed
            }
            Reply::Empty => {
                // gate: RT-G14 an empty reply counts as a failed turn
                self.bus.publish(TurnFailed { table: self.id.clone(), seat: label.clone(), error: "the reply was empty".into() });
                self.notice("error", format!("{label} sent an empty reply."));
                Outcome::Failed
            }
            Reply::Contribution(text) => self.submit(i, &text, after_work),
        };
        // A floor contribution sent to JEV is counted when JEV answers (see on_judged).
        if outcome == Outcome::Contributed && !after_work {
            return None;
        }
        // After work, the opportunity was counted when it started working; an acceptance now
        // still makes the round productive (on_judged does the same for judged replies).
        if after_work && outcome == Outcome::Accepted {
            self.rounds.record_accept();
        }
        (!after_work).then_some(outcome)
    }

    /// Block a message over the limit, else send it to JEV in the background. JEV is required
    /// (owner): nothing is shared without its verdict.
    pub(crate) fn submit(&mut self, i: usize, text: &str, after_work: bool) -> Outcome {
        let limit = self.seats[i].limit;
        // gate: RT-G02 reply length limit blocks
        // A message over the limit is blocked, never cut (owner). It does not go to JEV.
        let length = text.chars().count();
        if let Some(limit) = limit.filter(|limit| length > *limit) {
            self.seats[i].notices.push(prompts::too_long(length, limit));
            self.bus.publish(Contribution {
                table: self.id.clone(),
                seat: self.seats[i].label.clone(),
                id: None,
                text: text.to_string(),
                accepted: false,
                judged: false,
                scores: BTreeMap::new(),
                reasons: vec![format!("over the limit: {length} of {limit} characters")],
                limit: Some(limit),
                after_work,
                note: None,
            });
            return Outcome::Failed;
        }
        let judgement = Judgement { seat: i, text: text.to_string(), limit, after_work, topic: self.seats[i].prompt_topic, round: self.round_no };
        if !self.jev.configured() {
            self.not_evaluated(judgement, "JEV has no OpenRouter key".into());
            return Outcome::Failed;
        }
        // The owner's spec: the topic, the last rounds of accepted discussion, and the
        // contribution, within JEV's token limits. A contribution that cannot fit is an
        // operational error, not a rejection.
        let questions = jev::contribution_questions();
        let topic = self.topics[(judgement.topic - 1) as usize].clone();
        let state = match jev::contribution_state(&topic, &self.log, judgement.round, self.cfg.jev_history_rounds, &judgement.text, &questions) {
            Ok(state) => state,
            Err(reason) => {
                self.not_evaluated(judgement, reason);
                return Outcome::Failed;
            }
        };
        let ticket = self.ticket();
        if !judgement.after_work {
            // gate: RT-G10 the next turn waits for JEV's verdict
            self.judging_floor = Some(ticket);
        }
        self.judgements.insert(ticket, judgement);
        let jev = self.jev.clone();
        let internal = self.internal.clone();
        tokio::spawn(async move {
            let result = jev.ask(&state, &questions).await;
            let _ = internal.send(Internal::Judged { ticket, result });
        });
        Outcome::Contributed
    }

    pub(crate) fn on_judged(&mut self, ticket: u64, result: Result<BTreeMap<String, f64>, String>) {
        let Some(judgement) = self.judgements.remove(&ticket) else { return };
        let floor = self.judging_floor == Some(ticket);
        if floor {
            self.judging_floor = None;
        }
        // Floor turns are counted now; replies after work were counted when the agent started working.
        let count = |table: &mut Table, accepted: bool| {
            if floor {
                table.opportunity(Some(if accepted { Outcome::Accepted } else { Outcome::Contributed }));
            } else if accepted {
                table.rounds.record_accept();
            }
        };
        match result {
            Err(reason) => {
                self.not_evaluated(judgement, reason);
                count(self, false);
            }
            Ok(scores) => {
                // gate: RT-G01 the five message checks
                // Every failed check, in the owner's order: the gates, then the scores.
                let gates = jev::GATES.iter().map(|(name, _)| (*name, self.cfg.gate_pass));
                let checks = gates.chain(jev::SCORES.iter().map(|(name, _)| (*name, SCORE_PASS)));
                let failed: Vec<(String, f64)> =
                    checks.filter_map(|(name, pass)| scores.get(name).filter(|v| **v < pass).map(|v| (name.to_string(), *v))).collect();
                if failed.is_empty() {
                    self.accept(judgement, true, scores, None);
                    count(self, true);
                } else {
                    let i = judgement.seat;
                    self.seats[i].notices.push(prompts::rejected(&failed));
                    self.bus.publish(Contribution {
                        table: self.id.clone(),
                        seat: self.seats[i].label.clone(),
                        id: None,
                        text: judgement.text,
                        accepted: false,
                        judged: true,
                        scores,
                        reasons: failed.iter().map(|(name, value)| format!("{name} {value:.2}")).collect(),
                        limit: judgement.limit,
                        after_work: judgement.after_work,
                        note: None,
                    });
                    count(self, false);
                }
            }
        }
    }

    /// JEV could not evaluate a message: it is not shared, the chair sees the error at once and
    /// the author hears at its next turn. The table continues (owner: "If JEV is down this
    /// doesn't halt, it continues"). This is not a rejection, so no rejection feedback is made.
    // gate: RT-G01 a message JEV could not evaluate is not shared
    fn not_evaluated(&mut self, j: Judgement, reason: String) {
        let seat = self.seats[j.seat].label.clone();
        self.notice("error", format!("JEV could not evaluate {seat}'s message ({reason}); it was not shared."));
        self.seats[j.seat].notices.push(prompts::not_evaluated(&reason));
        self.bus.publish(Contribution {
            table: self.id.clone(),
            seat,
            id: None,
            text: j.text,
            accepted: false,
            judged: false,
            scores: BTreeMap::new(),
            reasons: vec![format!("not evaluated: {reason}")],
            limit: j.limit,
            after_work: j.after_work,
            note: None,
        });
    }

    pub(crate) fn accept(&mut self, j: Judgement, judged: bool, scores: BTreeMap<String, f64>, note: Option<String>) {
        let number = 1 + self.log.iter().filter(|e| matches!(e, Entry::Message { id, .. } if id.starts_with(&format!("R{}-", j.topic)))).count();
        let id = format!("R{}-{}", j.topic, number);
        let seat = &self.seats[j.seat];
        let name = seat.name.clone().unwrap_or_else(|| seat.label.clone());
        self.log.push(Entry::Message { id: id.clone(), seat: seat.label.clone(), name, text: j.text.clone(), round: j.round });
        self.bus.publish(Contribution {
            table: self.id.clone(),
            seat: self.seats[j.seat].label.clone(),
            id: Some(id),
            text: j.text,
            accepted: true,
            judged,
            scores,
            reasons: Vec::new(),
            limit: j.limit,
            after_work: j.after_work,
            note,
        });
    }
}
