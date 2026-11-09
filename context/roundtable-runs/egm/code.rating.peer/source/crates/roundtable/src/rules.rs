//! The Roundtable rules that involve no I/O: reply limits, reply kinds, rounds, topic scoring
//! and rating points. Every rule cites where it comes from (R = README.md, O = an owner
//! decision recorded in docs/TRACEABILITY.md).

use unicode_segmentation::UnicodeSegmentation;

/// Default reply limit in characters (owner's spec: 512). The chair sets it; agents cannot.
pub const DEFAULT_BASE: usize = 512;
/// Default limit for the one reply after an agent was skipped while busy (owner's spec: 1,024).
pub const DEFAULT_RECOVERY: usize = 1024;
/// Default number of rounds before the table ends (owner: 10). No limit is the building mode.
pub const DEFAULT_ROUNDS: u64 = 10;
/// Each yes/no gate passes at this confidence or higher (owner's spec: 0.7; restored by the owner
/// on 2026-11-07 once the owner's own questions were in place).
pub const GATE_PASS: f64 = 0.70;
/// Each 0-5 score passes at this value or higher (owner's spec: 3.0).
pub const SCORE_PASS: f64 = 3.0;
/// Topic proposals are bounded like any broadcast: the winner is sent to every agent (R §1.2; O).
pub const PROPOSAL_LIMIT: usize = 512;

/// Cut `text` to `limit` characters (Unicode scalar values) at a grapheme boundary: the text
/// kept and the number of characters removed. Length alone never rejects a contribution (R §4.5).
pub fn truncate_to(text: &str, limit: usize) -> (&str, usize) {
    let total = text.chars().count();
    if total <= limit {
        return (text, 0);
    }
    let (mut kept_bytes, mut kept_chars) = (0, 0);
    for grapheme in text.graphemes(true) {
        let chars = grapheme.chars().count();
        if kept_chars + chars > limit {
            break;
        }
        kept_chars += chars;
        kept_bytes += grapheme.len();
    }
    (&text[..kept_bytes], total - kept_chars)
}

/// What a participant's reply is. ACP has no pass method; the reply text says it.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Reply {
    /// Exactly `PASS` (R §4.3).
    Pass,
    Contribution(String),
    /// Nothing visible (run 1: 44 empty replies; recorded as a loud failure).
    Empty,
}

pub fn classify(reply: &str) -> Reply {
    let trimmed = reply.trim();
    if trimmed.is_empty() {
        Reply::Empty
    } else if trimmed.trim_end_matches('.').eq_ignore_ascii_case("pass") {
        Reply::Pass
    } else {
        Reply::Contribution(trimmed.to_string())
    }
}

/// One seat's outcome in a round.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Outcome {
    /// Accepted at once (judging off or JEV unavailable).
    Accepted,
    /// Sent to JEV; acceptance, if any, is added with [`RoundTracker::record_accept`].
    Contributed,
    Passed,
    /// Skipped because it was working; counts as passing (O: "two rounds of skips").
    SkippedWorking,
    Failed,
}

/// Counts rounds toward topic progression (R §6): two consecutive nonproductive rounds (no
/// accepted contribution), or two consecutive rounds in which every participant passed or
/// was skipped while working.
#[derive(Debug, Default, Clone)]
pub struct RoundTracker {
    accepted: usize,
    took_part: usize,
    passed: usize,
    nonproductive_streak: u32,
    all_pass_streak: u32,
}

impl RoundTracker {
    pub fn record(&mut self, outcome: Outcome) {
        self.took_part += 1;
        match outcome {
            Outcome::Accepted => self.accepted += 1,
            Outcome::Passed | Outcome::SkippedWorking => self.passed += 1,
            Outcome::Contributed | Outcome::Failed => {}
        }
    }

    /// A contribution accepted after JEV answered (or after the agent's work finished).
    pub fn record_accept(&mut self) {
        self.accepted += 1;
    }

    /// Close the round. True when the topic may advance.
    pub fn close_round(&mut self) -> bool {
        if self.took_part == 0 {
            return false;
        }
        self.nonproductive_streak = if self.accepted == 0 { self.nonproductive_streak + 1 } else { 0 };
        self.all_pass_streak = if self.passed == self.took_part { self.all_pass_streak + 1 } else { 0 };
        let (n, a) = (self.nonproductive_streak, self.all_pass_streak);
        *self = Self { nonproductive_streak: n, all_pass_streak: a, ..Self::default() };
        n >= 2 || a >= 2
    }

    pub fn reset(&mut self) {
        *self = Self::default();
    }
}

/// Pick the next topic (R §7.2-7.4). `confidence(i, j)` is JEV's confidence that proposals i
/// and j express the same intent. Each pair is credited to both and summed; the highest total
/// wins; tied winners are joined with " and ". Topics require JEV (O), so every pair here has
/// a judgment.
pub fn select_topic(proposals: &[String], confidence: impl Fn(usize, usize) -> f64) -> Option<(String, Vec<f64>)> {
    match proposals.len() {
        0 => None,
        1 => Some((proposals[0].clone(), vec![0.0])),
        n => {
            let mut totals = vec![0.0; n];
            for (i, j) in pairs(n) {
                let value = confidence(i, j);
                totals[i] += value;
                totals[j] += value;
            }
            let best = totals.iter().cloned().fold(f64::MIN, f64::max);
            let winners: Vec<&str> = proposals
                .iter()
                .zip(&totals)
                .filter(|(_, total)| (**total - best).abs() < 1e-9)
                .map(|(text, _)| text.trim())
                .collect();
            Some((winners.join(" and "), totals))
        }
    }
}

/// All unordered pairs of `n` proposals, each once: N(N-1)/2 (R §7.2).
pub fn pairs(n: usize) -> Vec<(usize, usize)> {
    (0..n).flat_map(|i| ((i + 1)..n).map(move |j| (i, j))).collect()
}

/// The owner's rating categories and weights (from the owner's earlier system): stars 0-5 in
/// each, scaled by weight / 5, plus 5 for the bonus. At most 105 points per rating.
pub const RATING_CATEGORIES: [(&str, f64); 4] =
    [("Efficient", 10.0), ("Alert & Aware", 20.0), ("Thorough", 30.0), ("Coordination", 40.0)];

pub fn rating_points(ratings: &serde_json::Map<String, serde_json::Value>) -> f64 {
    let stars: f64 = RATING_CATEGORIES
        .iter()
        .map(|(key, weight)| ratings.get(*key).and_then(|v| v.as_f64()).unwrap_or(0.0).clamp(0.0, 5.0) / 5.0 * weight)
        .sum();
    let bonus = if ratings.get("bonus").and_then(|v| v.as_bool()).unwrap_or(false) { 5.0 } else { 0.0 };
    stars + bonus
}

/// The line that starts each turn (owner): "Round N of T" until three rounds remain, then
/// "3 Rounds Remain", "2 Rounds Remain", "1 Round Remains" and "Final Round". With no limit,
/// "Round N".
pub fn round_label(round: u64, total: Option<u64>) -> String {
    match total.map(|t| t.saturating_sub(round)) {
        None => format!("Round {round}"),
        Some(0) => "Final Round".into(),
        Some(1) => "1 Round Remains".into(),
        Some(left @ (2 | 3)) => format!("{left} Rounds Remain"),
        Some(_) => format!("Round {round} of {}", total.unwrap_or_default()),
    }
}
