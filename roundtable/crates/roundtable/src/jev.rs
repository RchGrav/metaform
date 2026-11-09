//! JEV: one model that answers a question with a confidence, used as a programmatic if/case
//! (O). Required (owner, 2026-11-07): a call returns its answers or an error, and on error the
//! caller does not share the message and the table continues. No timer: "it gets a reply or
//! an error" (O).
//!
//! Each contribution is checked with one request of five questions, the owner's message
//! evaluation specification (7 November 2026): three yes/no gates and two 0-5 scores. The
//! texts are the owner's, kept in `resources/jev/`, with the code's field names in them.

use std::collections::BTreeMap;

use serde::Serialize;
use serde_json::{Value, json};

use crate::table::Entry;

pub const DECISIONS_URL: &str = "https://openrouter.ai/api/alpha/decisions";
/// The owner's choice: always the newest JEV release.
pub const DEFAULT_MODEL: &str = "~typesafe/jev-latest";

/// One question. A `noul` answers how sure JEV is that the answer is yes (0 to 1). A `score`
/// answers a position on the ordered levels in `criteria` (0 to the last level).
#[derive(Debug, Clone, Serialize)]
pub struct Question {
    #[serde(rename = "type")]
    pub kind: &'static str,
    pub instructions: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub criteria: Option<Vec<String>>,
}

fn noul(instructions: &str) -> Question {
    Question { kind: "noul", instructions: instructions.trim().into(), criteria: None }
}

/// A score file: the instructions, a blank line, then one level per line, lowest first.
fn score(text: &str) -> Question {
    let (instructions, levels) = text.split_once("\n\n").unwrap_or((text, ""));
    let criteria = levels.lines().map(str::trim).filter(|l| !l.is_empty()).map(String::from).collect();
    Question { kind: "score", instructions: instructions.trim().into(), criteria: Some(criteria) }
}

/// The three gates, in the order the author is told about them.
pub const GATES: [(&str, &str); 3] = [
    ("contribution", include_str!("../resources/jev/contribution.md")),
    ("usefulness", include_str!("../resources/jev/usefulness.md")),
    ("relevance", include_str!("../resources/jev/relevance.md")),
];

/// The two scores, after the gates in that order.
pub const SCORES: [(&str, &str); 2] = [
    ("value", include_str!("../resources/jev/value.md")),
    ("auditability", include_str!("../resources/jev/auditability.md")),
];

pub fn contribution_questions() -> BTreeMap<String, Question> {
    let gates = GATES.iter().map(|(name, text)| (name.to_string(), noul(text)));
    let scores = SCORES.iter().map(|(name, text)| (name.to_string(), score(text)));
    gates.chain(scores).collect()
}

/// Completed rounds of discussion JEV sees, plus the current round so far (owner's spec). The
/// default of the `jev.history_rounds` setting is declared to match.
pub const HISTORY_ROUNDS: u64 = 4;
/// The state plus the longest single question must fit in this many tokens (owner's spec).
pub const STATE_PLUS_QUESTION_TOKENS: usize = 32_000;
/// The whole request must fit in this many tokens (owner's spec).
pub const REQUEST_TOKENS: usize = 64_000;

/// An estimate, not the provider's count: one token per 3 bytes of JSON. English text runs about
/// 4 bytes per token, so this estimate counts high and leaves a margin.
pub fn estimate_tokens(value: &impl Serialize) -> usize {
    serde_json::to_string(value).map(|s| s.len().div_ceil(3)).unwrap_or(usize::MAX)
}

/// JEV's state for one message: the topic, the accepted discussion of the last
/// [`HISTORY_ROUNDS`] completed rounds and the current round, grouped by round, and the new
/// message's text, named `new_message` as the owner's questions call it. The oldest messages are left out until both token limits are met. `Err` when
/// even an empty conversation does not fit.
pub(crate) fn contribution_state(topic: &str, log: &[Entry], round: u64, history_rounds: u64, new_message: &str, questions: &BTreeMap<String, Question>) -> Result<Value, String> {
    // gate: RT-G17 JEV sees only the recent rounds
    let first = round.saturating_sub(history_rounds);
    let mut entries: Vec<(u64, Value)> = log
        .iter()
        .filter_map(|entry| match entry {
            Entry::Message { id, name, text, round, .. } if *round >= first => Some((*round, json!({"id": id, "name": name, "text": text}))),
            Entry::Chair { text, round } if *round >= first => Some((*round, json!({"name": "Chair", "text": text}))),
            _ => None,
        })
        .collect();
    let longest = questions.values().map(estimate_tokens).max().unwrap_or(0);
    let all = estimate_tokens(questions);
    loop {
        let state = json!({"topic": topic, "conversation": by_round(&entries), "new_message": new_message});
        let size = estimate_tokens(&state);
        if size + longest <= STATE_PLUS_QUESTION_TOKENS && size + all <= REQUEST_TOKENS {
            return Ok(state);
        }
        if entries.is_empty() {
            return Err(format!("the contribution does not fit JEV's limits (about {size} tokens of state)"));
        }
        // gate: RT-G17 the oldest messages are left out to meet JEV's token limits
        entries.remove(0);
    }
}

fn by_round(entries: &[(u64, Value)]) -> Vec<Value> {
    let mut rounds: Vec<Value> = Vec::new();
    for (round, message) in entries {
        match rounds.last_mut() {
            Some(last) if last["round"] == *round => last["messages"].as_array_mut().expect("messages").push(message.clone()),
            _ => rounds.push(json!({"round": round, "messages": [message]})),
        }
    }
    rounds
}

/// The owner's topic comparison, kept in `resources/topic_sameness.md` so the owner can edit it.
/// `{{foo}}` and `{{bar}}` become the two proposals' names in the state (`proposals.p0`, ...).
pub const TOPIC_SAMENESS: &str = include_str!("../resources/topic_sameness.md");

/// R §7.1: one statement per pair of proposed topics.
pub fn sameness_question(a: usize, b: usize) -> Question {
    noul(&TOPIC_SAMENESS.replacen("{{foo}}", &format!("`proposals.p{a}`"), 1).replacen("{{bar}}", &format!("`proposals.p{b}`"), 1))
}

#[derive(Debug, Clone)]
pub struct Jev {
    client: reqwest::Client,
    key: Option<String>,
    pub model: String,
    pub url: String,
}

impl Jev {
    pub fn new(client: reqwest::Client, key: Option<String>) -> Self {
        Self { client, key: key.filter(|k| !k.trim().is_empty()), model: DEFAULT_MODEL.into(), url: DECISIONS_URL.into() }
    }

    pub fn configured(&self) -> bool {
        self.key.is_some()
    }

    pub fn key(&self) -> Option<&str> {
        self.key.as_deref()
    }

    pub fn set_key(&mut self, key: Option<String>) {
        self.key = key.filter(|k| !k.trim().is_empty());
    }

    /// Ask `questions` about `state`: each answer by question name, a noul from 0 to 1 or a
    /// score from 0 to its last level. `Err` says why JEV could not answer.
    pub async fn ask(&self, state: &Value, questions: &BTreeMap<String, Question>) -> Result<BTreeMap<String, f64>, String> {
        let key = self.key.as_deref().ok_or("no OpenRouter key configured")?;
        let body = json!({"model": self.model, "state": state, "questions": questions});
        let response = self.client.post(&self.url).bearer_auth(key).json(&body).send().await.map_err(|e| e.to_string())?;
        let status = response.status();
        let text = response.text().await.map_err(|e| e.to_string())?;
        if !status.is_success() {
            return Err(format!("HTTP {status}: {}", text.chars().take(300).collect::<String>()));
        }
        let reply: Value = serde_json::from_str(&text).map_err(|e| format!("unreadable answer: {e}"))?;
        let mut found = BTreeMap::new();
        for (name, question) in questions {
            let top = match &question.criteria {
                Some(levels) if question.kind == "score" => levels.len().saturating_sub(1) as f64,
                _ => 1.0,
            };
            let value = reply["answers"][name][question.kind].as_f64().ok_or(format!("no {} answer for {name}", question.kind))?;
            if !(0.0..=top).contains(&value) {
                return Err(format!("{name} answer {value} is outside 0..{top}"));
            }
            found.insert(name.clone(), value);
        }
        Ok(found)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn message(round: u64, n: usize, text: String) -> Entry {
        Entry::Message { id: format!("R1-{n}"), seat: "Bo".into(), name: "Bo".into(), text, round }
    }

    // Owner's spec: the five questions, and JEV sees the last four completed rounds plus the
    // current round, with the oldest messages left out first to meet the token limits.
    #[test]
    fn the_state_holds_four_completed_rounds_and_the_current_one_within_the_limits() {
        let questions = contribution_questions();
        assert_eq!(questions.len(), 5);
        assert_eq!(questions["value"].criteria.as_ref().unwrap().len(), 6);
        assert_eq!(questions["auditability"].criteria.as_ref().unwrap().len(), 6);
        assert!(questions["relevance"].criteria.is_none());

        let log: Vec<Entry> = (1..=10).map(|r| message(r, r as usize, format!("round {r}"))).collect();
        let state = contribution_state("t", &log, 10, HISTORY_ROUNDS, "x", &questions).unwrap();
        let rounds: Vec<u64> = state["conversation"].as_array().unwrap().iter().map(|r| r["round"].as_u64().unwrap()).collect();
        assert_eq!(rounds, vec![6, 7, 8, 9, 10]);

        let big: Vec<Entry> = (0..40).map(|n| message(10, n, "é".repeat(2000))).collect();
        let state = contribution_state("t", &big, 10, HISTORY_ROUNDS, "x", &questions).unwrap();
        let kept = state["conversation"][0]["messages"].as_array().unwrap();
        assert!(kept.len() < 40 && kept.last().unwrap()["id"] == "R1-39", "the newest messages are kept");
        assert!(estimate_tokens(&state) + estimate_tokens(&questions) <= REQUEST_TOKENS);
    }
}
