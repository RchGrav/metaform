//! Text sent to participants. The roundtable prompt and the participant prompt are the owner's
//! templates, verbatim. The per-turn format is the owner's (O): the round line, the truncation
//! notice, the rejection reasons, each agent's message, then the characters line. Everything sent to every agent costs once per seat (R §1.2), so the
//! surrounding text is kept short.

/// The owner's participant prompt (supplied 2026-11-05; supersedes the R §3 wording), kept
/// verbatim in `resources/participant_prompt.md` so the owner can edit it directly.
/// `{{roundtable_prompt}}` takes the user's objective; see [`participant_prompt`].
pub const PARTICIPANT_PROMPT: &str = include_str!("../resources/participant_prompt.md");

/// The participant prompt with its placeholders filled.
pub fn participant_prompt(objective: &str) -> String {
    PARTICIPANT_PROMPT.replacen("{{roundtable_prompt}}", objective, 1)
}

/// A message over the reply limit is blocked, never cut (owner). Builder wording, kept in
/// `resources/feedback/too_long.md` for the owner to replace.
pub fn too_long(length: usize, limit: usize) -> String {
    include_str!("../resources/feedback/too_long.md").replace("{{length}}", &length.to_string()).replace("{{limit}}", &limit.to_string())
}

/// The owner's rejection feedback (message evaluation specification, `resources/feedback/`):
/// the prefix, one line per failed gate, and one line per failed score from the band it fell in.
const PREFIX: &str = include_str!("../resources/feedback/prefix.md");

fn feedback(name: &str, result: f64) -> &'static str {
    match (name, result as u64) {
        ("contribution", _) => include_str!("../resources/feedback/contribution.md"),
        ("usefulness", _) => include_str!("../resources/feedback/usefulness.md"),
        ("relevance", _) => include_str!("../resources/feedback/relevance.md"),
        ("value", 0) => include_str!("../resources/feedback/value-0.md"),
        ("value", 1) => include_str!("../resources/feedback/value-1.md"),
        ("value", _) => include_str!("../resources/feedback/value-2.md"),
        ("auditability", 0) => include_str!("../resources/feedback/auditability-0.md"),
        ("auditability", 1) => include_str!("../resources/feedback/auditability-1.md"),
        ("auditability", _) => include_str!("../resources/feedback/auditability-2.md"),
        _ => "",
    }
}

/// R §4.6: the disposition and the reasons, at the next turn. `failed` holds each failed check
/// with JEV's result, in the owner's order: contribution, usefulness, relevance, value,
/// auditability. The lines follow the owner's example: "- Contribution: <feedback>".
pub fn rejected(failed: &[(String, f64)]) -> String {
    let lines: Vec<String> = failed
        .iter()
        .map(|(name, result)| {
            let mut label = name.clone();
            label[..1].make_ascii_uppercase();
            format!("- {label}: {}", feedback(name, *result).trim())
        })
        .collect();
    format!("{PREFIX}\n{}", lines.join("\n"))
}

/// The owner's roundtable prompt (message evaluation specification), kept verbatim in
/// `resources/roundtable_prompt.md`. Sent once, on an agent's first turn.
pub const ROUNDTABLE_PROMPT: &str = include_str!("../resources/roundtable_prompt.md");

/// What fills the roundtable prompt's placeholders.
pub struct Fill<'a> {
    pub agent_name: &'a str,
    pub topic: &'a str,
    /// The owner's participant prompt, already filled: `{{custom_roundtable_prompt}}`.
    pub custom: &'a str,
    pub workspace: &'a str,
    /// The turn itself: the round line, notices and the other agents' messages.
    pub delivery: &'a str,
}

/// The roundtable prompt with its placeholders filled. The free text (topic, custom prompt and
/// delivery) goes in last, so text inside it that looks like a placeholder is left alone.
pub fn roundtable_prompt(fill: &Fill) -> String {
    ROUNDTABLE_PROMPT
        .replace("{{AgentName}}", fill.agent_name)
        .replace("{{artifact_directory}}", fill.workspace)
        .replacen("{{roundtable_subject}}", "\u{0}topic\u{0}", 1)
        .replacen("{{custom_roundtable_prompt}}", "\u{0}custom\u{0}", 1)
        .replacen("{{delivery_json}}", "\u{0}delivery\u{0}", 1)
        .replacen("\u{0}topic\u{0}", fill.topic, 1)
        .replacen("\u{0}custom\u{0}", fill.custom, 1)
        .replacen("\u{0}delivery\u{0}", fill.delivery, 1)
}

pub fn topic_proposal() -> String {
    format!("The current topic is complete. Propose the next topic, in at most {} characters. Reply with only the proposal.", crate::rules::PROPOSAL_LIMIT)
}

/// O: "if one agent is idle and the others are busy it should be told to review materials".
pub const REVIEW: &str = "The other participants are working right now. While you wait, review the materials in the shared workspace.";

/// The owner's roundtable scoring prompt, verbatim (spacing and punctuation included) from
/// `archaeology/docs/reference/roundtable-agent-ratings.md`, "Exact roundtable scoring prompt".
/// `<seats/>` takes the other participants' names.
pub const SESSION_SCORING: &str = include_str!("../resources/session_scoring.md");

/// The owner's scoring messages, verbatim from the same document: the receipt for a card, the
/// results (`<ranking/>` takes one `session_rank` line per participant), and the profile line a
/// returning identity receives.
pub const SCORE_RECEIVED: &str = include_str!("../resources/score_received.md");
pub const SESSION_RESULTS: &str = include_str!("../resources/session_results.md");
pub const SESSION_RANK: &str = include_str!("../resources/session_rank.md");
pub const SESSION_PROFILE: &str = include_str!("../resources/session_profile.md");

/// Points as the owner's examples write them: whole numbers bare, otherwise one decimal.
pub fn points(value: f64) -> String {
    if (value - value.round()).abs() < 1e-9 { format!("{value:.0}") } else { format!("{value:.1}") }
}

/// The scoring prompt for a participant, naming the others it rates.
pub fn rating_request(others: &[String]) -> String {
    SESSION_SCORING.replacen("<seats/>", &others.join(", "), 1)
}
