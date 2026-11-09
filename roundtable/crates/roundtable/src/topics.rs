//! The next-topic poll (only with JEV, O): asking for proposals, judging them, changing topic.

use std::collections::{BTreeMap, HashSet};

use crate::table::{Activity, Entry, Internal, Polling, SeatState, Table};
use crate::events::*;
use crate::jev;
use crate::prompts;
use crate::rules::{self, Reply};


impl Table {
    /// Poll every participant for a next-topic proposal (R §7: "All participating agents are
    /// polled"). Free ones are asked now; busy ones when they become free.
    pub(crate) fn start_polling(&mut self) {
        self.topic_due = false;
        // Every participant is polled (R §7): free ones now, busy ones when their prompt ends.
        let mut waiting = HashSet::new();
        let mut pending = HashSet::new();
        let mut polled = Vec::new();
        for i in 0..self.seats.len() {
            if self.seats[i].state != SeatState::Ready {
                continue;
            }
            if self.seats[i].activity != Activity::Idle {
                if !self.cfg.poll_busy_agents {
                    continue; // owner: "the table never waits on independent work"
                }
                // gate: RT-G21 a topic poll waits for busy agents
                pending.insert(i);
                polled.push(self.seats[i].label.clone());
            } else if self.offer(i, Some(prompts::topic_proposal(self.cfg.topic_proposal_limit)), Activity::Proposing) {
                waiting.insert(i);
                polled.push(self.seats[i].label.clone());
            }
        }
        self.bus.publish(TopicPolling { table: self.id.clone(), seats: polled });
        let asked = waiting.iter().chain(pending.iter()).copied().collect();
        self.polling = Some(Polling { proposals: Vec::new(), asked, waiting, pending, scoring: None });
    }

    /// A seat that was busy when the poll began is asked once its prompt has ended; one that
    /// left the table is no longer waited for.
    pub(crate) fn settle_poll(&mut self, i: usize) {
        let Some(polling) = self.polling.as_mut() else { return };
        if !polling.pending.contains(&i) || polling.scoring.is_some() {
            return;
        }
        if self.seats[i].state != SeatState::Ready {
            polling.pending.remove(&i);
            return;
        }
        if self.seats[i].activity != Activity::Idle {
            return;
        }
        polling.pending.remove(&i);
        if self.offer(i, Some(prompts::topic_proposal(self.cfg.topic_proposal_limit)), Activity::Proposing)
            && let Some(polling) = self.polling.as_mut()
        {
            polling.waiting.insert(i);
        }
    }

    pub(crate) fn on_proposal(&mut self, i: usize, reply: &str) {
        let label = self.seats[i].label.clone();
        let late = match self.polling.as_ref() {
            None => Some("after the poll ended"),
            Some(p) if !p.asked.contains(&i) => Some("after the poll it answered had ended"),
            Some(p) if p.scoring.is_some() => Some("after the proposals went to JEV"),
            Some(_) => None,
        };
        if let Some(when) = late {
            // gate: RT-G12 a late topic proposal is discarded
            self.notice("info", format!("{label}'s topic proposal arrived {when} and was not counted."));
            return;
        }
        let polling = self.polling.as_mut().expect("checked above");
        polling.waiting.remove(&i);
        match rules::classify(reply) {
            Reply::Contribution(text) => {
                let length = text.chars().count();
                // gate: RT-G13 a topic proposal over its limit is blocked, never cut (owner)
                if let Some(limit) = self.cfg.topic_proposal_limit.filter(|&limit| length > limit) {
                    self.seats[i].notices.push(prompts::too_long(length, limit));
                    self.notice("info", format!("{label}'s topic proposal had {length} characters, over the limit of {limit}, and was not counted."));
                    return;
                }
                polling.proposals.push((i, text.clone()));
                self.bus.publish(TopicProposed { table: self.id.clone(), seat: label, text });
            }
            Reply::Pass => {}
            // F14: an empty proposal is a failed request, reported like an empty turn.
            Reply::Empty => {
                self.bus.publish(TurnFailed { table: self.id.clone(), seat: label.clone(), error: "the topic proposal was empty".into() });
                self.notice("error", format!("{label} sent an empty topic proposal."));
            }
        }
    }

    pub(crate) fn finish_polling(&mut self) {
        // Seat order, so ties join in seat order whatever order the proposals arrived in.
        if let Some(p) = self.polling.as_mut() {
            p.proposals.sort_by_key(|(i, _)| *i);
        }
        let Some(polling) = self.polling.as_ref() else { return };
        let proposals: Vec<String> = polling.proposals.iter().map(|(_, t)| t.clone()).collect();
        match proposals.len() {
            0 => {
                self.polling = None;
                self.notice("info", "No topic proposals arrived; the current topic continues.");
                self.rounds.reset();
                self.round_left = self.seats.len();
            }
            1 => self.complete_polling(BTreeMap::new()),
            _ => {
                let questions = rules::pairs(proposals.len())
                    .into_iter()
                    .map(|(a, b)| (format!("p{a}_{b}"), jev::sameness_question(a, b)))
                    .collect();
                let named: serde_json::Map<String, serde_json::Value> =
                    proposals.iter().enumerate().map(|(i, text)| (format!("p{i}"), serde_json::Value::from(text.as_str()))).collect();
                let state = serde_json::json!({"proposals": named});
                let ticket = self.ticket();
                if let Some(p) = self.polling.as_mut() {
                    p.scoring = Some(ticket);
                }
                let jev = self.jev.clone();
                let internal = self.internal.clone();
                tokio::spawn(async move {
                    let result = jev.ask(&state, &questions).await;
                    let _ = internal.send(Internal::Scored { ticket, result });
                });
            }
        }
    }

    pub(crate) fn on_scored(&mut self, ticket: u64, result: Result<BTreeMap<String, f64>, String>) {
        if self.polling.as_ref().and_then(|p| p.scoring) != Some(ticket) {
            return;
        }
        match result {
            Ok(found) => self.complete_polling(found),
            Err(reason) => {
                // Topics require JEV (O): without its judgment there is no topic change.
                self.polling = None;
                self.notice("error", format!("JEV could not compare the topic proposals ({reason}); the current topic continues."));
                self.rounds.reset();
                self.round_left = self.seats.len();
            }
        }
    }

    pub(crate) fn complete_polling(&mut self, judged: BTreeMap<String, f64>) {
        let Some(polling) = self.polling.take() else { return };
        // Pair keys were built in this same (seat) order in finish_polling.
        let proposals: Vec<String> = polling.proposals.iter().map(|(_, t)| t.clone()).collect();
        let Some((winner, totals)) = rules::select_topic(&proposals, |a, b| judged.get(&format!("p{a}_{b}")).copied().unwrap_or(0.0)) else { return };
        let scores = polling.proposals.iter().zip(totals).map(|((i, _), t)| (self.seats[*i].label.clone(), t)).collect();
        self.change_topic(winner, "selected from proposals".into(), scores);
    }

    pub(crate) fn change_topic(&mut self, topic: String, how: String, scores: Vec<(String, f64)>) {
        let accepted = self.log.iter().any(|e| matches!(e, Entry::Message { id, .. } if id.starts_with(&format!("R{}-", self.topic_index))));
        if accepted || self.worked_in_topic {
            self.idle_topics = 0;
        } else {
            self.idle_topics += 1;
            if self.idle_topics == 2 {
                // Observed: ~1,590 topic cycles in seconds when every agent passed. Information only.
                self.notice("warn", "Two topics in a row ended with nothing accepted and no work. The table keeps running and spending on each turn; hold or end it if the work is done.");
            }
        }
        self.worked_in_topic = self.seats.iter().any(|s| matches!(s.activity, Activity::Working(_)));
        self.topics.push(topic.clone());
        self.topic_index = self.topics.len() as u64;
        self.rounds.reset();
        self.round_left = self.seats.len();
        self.topic_due = false;
        self.bus.publish(TopicChanged { table: self.id.clone(), index: self.topic_index, topic, how, scores });
    }
}
