//! The rating round at the end of a table (O): scorecards, points and the results message.

use std::collections::HashSet;

use crate::table::{Activity, SeatState, Table};
use crate::events::*;
use crate::prompts;
use crate::rules::{self};


impl Table {
    /// End of the table: every participant rates every other (O). One that is busy is asked
    /// when its current prompt finishes; End again stops the table at once.
    pub(crate) fn start_rating(&mut self) {
        let left: HashSet<usize> = (0..self.seats.len()).filter(|&i| self.seats[i].state == SeatState::Ready && self.seats[i].name.is_some()).collect();
        if left.len() < 2 {
            // not a gate: the chair ended the table and fewer than two agents can rate
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
                        // gate: RT-G15 a rating card must be a JSON object
                        self.notice("error", format!("{from}'s rating for {to_name:?} is not a JSON object; not recorded."));
                        continue;
                    };
                    unrated.retain(|n| n != to_name);
                    let targets: Vec<usize> = (0..self.seats.len()).filter(|&j| j != i && self.seats[j].name.as_deref() == Some(to_name.as_str())).collect();
                    if targets.len() != 1 {
                        // gate: RT-G15 a rating must name exactly one participant
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
                // gate: RT-G15 ratings must be readable JSON
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
    pub(crate) fn finish_ratings(&mut self) {
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
    pub(crate) fn check_results_done(&mut self) {
        if self.ranking.is_none() || self.ended {
            return;
        }
        let waiting = self.seats.iter().enumerate().any(|(i, s)| {
            s.state == SeatState::Ready && s.name.is_some() && (matches!(s.activity, Activity::Notified(_)) || !self.results_sent.contains(&i))
        });
        if !waiting {
            // not a gate: the chair's End finishes after the results are sent
            self.end("ended by the chair");
        }
    }
}
