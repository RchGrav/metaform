//! Inside an opportunity: the prompt a seat receives (O format), how its reply is resolved,
//! judging (which never holds the table, R §4), the next-topic poll (only with JEV, O), and
//! the rating round at the end (O).

use std::collections::{BTreeMap, HashSet};

use crate::engine::{Activity, Entry, Internal, Judgement, Polling, SeatState, Table};
use crate::events::*;
use crate::jev;
use crate::prompts;
use crate::rules::{self, GATE_PASS, Outcome, PROPOSAL_LIMIT, Reply, SCORE_PASS};

/// What a prompt consumed; applied only once the prompt was actually sent.
pub(crate) struct Commit {
    log: usize,
    topic: u64,
    /// The notices went out with this prompt.
    notices: bool,
}

impl Table {
    /// The prompt for seat `i`, in the owner's order: the round line, the truncation notice, the
    /// rejection reasons, each other participant's message, then the characters line (O). Only
    /// what is new since its last turn; its ACP session keeps the rest. `ask` replaces the
    /// characters line for special requests (review, topic proposal, ratings). `discussion`: a
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

    /// Truncate, then judge in the background or share at once (judging off or no key).
    fn submit(&mut self, i: usize, text: &str, after_work: bool) -> Outcome {
        let limit = self.seats[i].limit;
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
        if !self.judging {
            self.accept(judgement, false, BTreeMap::new(), Some("unjudged: judging is off".into()));
            return Outcome::Accepted;
        }
        if !self.jev.configured() {
            self.accept(judgement, false, BTreeMap::new(), Some("unjudged: no OpenRouter key".into()));
            return Outcome::Accepted;
        }
        // The owner's spec: the topic, the last rounds of accepted discussion, and the
        // contribution, within JEV's token limits. A contribution that cannot fit is an
        // operational error, shared unjudged and shown loudly, not a rejection.
        let questions = jev::contribution_questions();
        let topic = self.topics[(judgement.topic - 1) as usize].clone();
        let state = match jev::contribution_state(&topic, &self.log, judgement.round, &judgement.text, &questions) {
            Ok(state) => state,
            Err(reason) => {
                self.notice("error", format!("JEV could not judge {}'s message ({reason}); it was shared unjudged.", self.seats[i].label));
                self.accept(judgement, false, BTreeMap::new(), Some(format!("unjudged: {reason}")));
                return Outcome::Accepted;
            }
        };
        let ticket = self.ticket();
        if !judgement.after_work {
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
                self.notice("error", format!("JEV could not judge {}'s message ({reason}); it was shared unjudged.", self.seats[judgement.seat].label));
                self.accept(judgement, false, BTreeMap::new(), Some(format!("unjudged: JEV unavailable ({reason})")));
                count(self, true);
            }
            Ok(scores) => {
                // Every failed check, in the owner's order: the gates, then the scores.
                let gates = jev::GATES.iter().map(|(name, _)| (*name, GATE_PASS));
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

    fn accept(&mut self, j: Judgement, judged: bool, scores: BTreeMap<String, f64>, note: Option<String>) {
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
                pending.insert(i);
                polled.push(self.seats[i].label.clone());
            } else if self.offer(i, Some(prompts::topic_proposal()), Activity::Proposing) {
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
        if self.offer(i, Some(prompts::topic_proposal()), Activity::Proposing)
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
            self.notice("info", format!("{label}'s topic proposal arrived {when} and was not counted."));
            return;
        }
        let polling = self.polling.as_mut().expect("checked above");
        polling.waiting.remove(&i);
        match rules::classify(reply) {
            Reply::Contribution(text) => {
                let text = rules::truncate_to(&text, PROPOSAL_LIMIT).0.to_string();
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

    fn complete_polling(&mut self, judged: BTreeMap<String, f64>) {
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

    /// End of the table: every participant rates every other (O). One that is busy is asked
    /// when its current prompt finishes; End again stops the table at once.
    pub(crate) fn start_rating(&mut self) {
        let left: HashSet<usize> = (0..self.seats.len()).filter(|&i| self.seats[i].state == SeatState::Ready && self.seats[i].name.is_some()).collect();
        if left.len() < 2 {
            self.end("ended by the chair");
            return;
        }
        self.bus.publish(RatingsAsked { table: self.id.clone(), seats: left.iter().map(|&i| self.seats[i].label.clone()).collect() });
        self.rating = Some((left.clone(), HashSet::new()));
        for i in left {
            if self.seats[i].activity == Activity::Idle {
                self.ask_to_rate(i);
            }
        }
    }

    pub(crate) fn ask_to_rate(&mut self, i: usize) {
        let Some(me) = self.seats[i].name.clone() else { return };
        let others: Vec<String> = self.names().into_iter().filter(|n| *n != me).collect();
        if let Some((_, asked)) = self.rating.as_mut() {
            asked.insert(i);
        }
        if !self.offer(i, Some(prompts::rating_request(&others)), Activity::Rating) {
            self.rating_done(i);
        }
    }

    pub(crate) fn on_rating(&mut self, i: usize, reply: &str) {
        let from = self.seats[i].label.clone();
        let from_name = self.seats[i].name.clone().unwrap_or_else(|| from.clone());
        let json = reply.find('{').zip(reply.rfind('}')).and_then(|(a, b)| serde_json::from_str::<serde_json::Value>(&reply[a..=b]).ok());
        // Everyone this rater was asked to rate (the request names them).
        let mut unrated: Vec<String> = self.names().into_iter().filter(|n| *n != from_name).collect();
        match json.as_ref().and_then(|v| v.as_object()) {
            Some(cards) => {
                for (to_name, card) in cards {
                    let Some(ratings) = card.as_object() else {
                        // Fail loudly: a card that is not an object is not a rating (round 3, N01).
                        self.notice("error", format!("{from}'s rating for {to_name:?} is not a JSON object; not recorded."));
                        continue;
                    };
                    unrated.retain(|n| n != to_name);
                    let targets: Vec<usize> = (0..self.seats.len()).filter(|&j| j != i && self.seats[j].name.as_deref() == Some(to_name.as_str())).collect();
                    if targets.len() != 1 {
                        self.notice("error", format!("{from} rated {to_name:?}, which matches {} participants; not recorded.", targets.len()));
                        continue;
                    }
                    let to = self.seats[targets[0]].label.clone();
                    let to_session = self.seats[targets[0]].session.clone();
                    let points = rules::rating_points(ratings);
                    let entry = self.session_points.entry(targets[0]).or_insert((0.0, 0));
                    entry.0 += points;
                    entry.1 += 1;
                    self.bus.publish(RatingGiven {
                        table: self.id.clone(),
                        from: from.clone(),
                        from_name: from_name.clone(),
                        to,
                        to_name: to_name.clone(),
                        to_session,
                        ratings: ratings.clone(),
                        points,
                    });
                }
            }
            None => {
                self.notice("error", format!("{from}'s ratings could not be read as JSON; not recorded."));
                unrated.clear(); // already reported as a whole
            }
        }
        // F14: the owner's peer ratings are required, so a missing one is reported, not
        // passed over (no retry: the rater is not asked again).
        if !unrated.is_empty() {
            self.notice("error", format!("{from} did not rate {}; those ratings are missing.", unrated.join(", ")));
        }
        // The owner's receipt for a scorecard that was read.
        if json.as_ref().is_some_and(|v| v.is_object()) {
            self.offer(i, Some(prompts::SCORE_RECEIVED.to_string()), Activity::Notified);
        }
        self.rating_done(i);
    }

    pub(crate) fn rating_done(&mut self, i: usize) {
        if let Some((left, _)) = self.rating.as_mut()
            && left.remove(&i)
            && left.is_empty()
        {
            self.finish_ratings();
        }
    }

    /// Every scorecard is in: each participant still at the table gets the owner's results
    /// message (the scoring prompt promised it), then the table ends.
    fn finish_ratings(&mut self) {
        let mut rows: Vec<(f64, String)> = Vec::new();
        for (i, seat) in self.seats.iter().enumerate() {
            let Some(name) = seat.name.clone() else { continue };
            let (points, cards) = self.session_points.get(&i).copied().unwrap_or((0.0, 0));
            let prior = match self.identities.as_ref().map(|store| store.profile(&seat.session)) {
                Some(Ok(profile)) => profile.filter(|p| p.ratings > 0),
                Some(Err(error)) => {
                    self.notice("error", format!("{name}'s identity profile could not be read: {error}"));
                    None
                }
                None => None,
            };
            // An identity is unscored until it receives a rating (owner's scoring reference).
            let rating = match (prior, cards) {
                (None, 0) => "unscored".to_string(),
                (prior, _) => prompts::points(prior.map(|p| p.score).unwrap_or(0.0) + points),
            };
            let line = prompts::SESSION_RANK
                .replacen("<seat/>", &name, 1)
                .replacen("<points/>", &prompts::points(points), 1)
                .replacen("<cards/>", &cards.to_string(), 1)
                .replacen("<rating/>", &rating, 1);
            rows.push((points, line));
        }
        // The session ranking sorts by points received this session (a sum, not an average).
        rows.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap_or(std::cmp::Ordering::Equal));
        let ranking = rows.into_iter().map(|(_, line)| line).collect::<Vec<_>>().join("\n");
        self.ranking = Some(prompts::SESSION_RESULTS.replacen("<ranking/>", &ranking, 1));
        for i in 0..self.seats.len() {
            self.settle_results(i);
        }
        self.check_results_done();
    }

    /// Send seat `i` the results once they exist, it is still at the table and it is free.
    pub(crate) fn settle_results(&mut self, i: usize) {
        let Some(results) = self.ranking.clone() else { return };
        let seat = &self.seats[i];
        if seat.state == SeatState::Ready && seat.name.is_some() && seat.activity == Activity::Idle && !self.results_sent.contains(&i) {
            self.results_sent.insert(i);
            self.offer(i, Some(results), Activity::Notified);
        }
        self.check_results_done();
    }

    /// The table ends once every participant still present was sent the results and no
    /// scoring message is still being answered.
    fn check_results_done(&mut self) {
        if self.ranking.is_none() || self.ended {
            return;
        }
        let waiting = self.seats.iter().enumerate().any(|(i, s)| {
            s.state == SeatState::Ready && s.name.is_some() && (matches!(s.activity, Activity::Notified(_)) || !self.results_sent.contains(&i))
        });
        if !waiting {
            self.end("ended by the chair");
        }
    }
}
