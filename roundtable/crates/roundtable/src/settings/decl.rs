//! The declarations. Each setting is listed here once, with its default, its gate and how it
//! reaches a table's configuration.

use acp_host::Rule;

use super::{Kind, Setting, Value};

const MANY: u64 = 1_000_000;
const RULES: &[&str] = &["inside", "allow", "refuse"];

fn count(v: &Value) -> Option<usize> {
    v.as_count().map(|n| n as usize)
}

fn rule(v: &Value) -> Rule {
    match v {
        Value::Word(w) if w == "allow" => Rule::Allow,
        Value::Word(w) if w == "refuse" => Rule::Refuse,
        _ => Rule::Inside,
    }
}

/// The folder a "project" scope means: the nearest folder at or above the workspace that holds
/// a `.git` entry; the workspace itself when there is none.
fn project_root(workspace: &std::path::Path) -> std::path::PathBuf {
    workspace.ancestors().find(|dir| dir.join(".git").exists()).unwrap_or(workspace).to_path_buf()
}

macro_rules! permission {
    ($kind:literal) => {
        Setting {
            key: concat!("permissions.", $kind),
            kind: Kind::Choice(RULES),
            default: "inside",
            summary: concat!(
                "How an agent's ",
                $kind,
                " requests are answered: inside (allowed when every path named is inside the scope), allow, or refuse."
            ),
            gate: Some("RT-G18"),
            apply: |c, v| {
                c.permissions.0.insert($kind.to_string(), rule(v));
            },
        }
    };
}

pub static SETTINGS: &[Setting] = &[
    Setting {
        key: "table.rounds",
        kind: Kind::CountOrOff { min: 1, max: MANY },
        default: "10",
        summary: "How many rounds a table runs before the rating round; off for no limit.",
        gate: Some("RT-G05"),
        apply: |c, v| c.rounds = v.as_count(),
    },
    Setting {
        key: "table.quiet_rounds",
        kind: Kind::Count { min: 1, max: 100 },
        default: "2",
        summary: "How many rounds in a row with nothing accepted end a table with no round limit, or start a topic poll when topics are on.",
        gate: Some("RT-G06"),
        apply: |c, v| c.quiet_rounds = v.as_count().unwrap_or(2) as u32,
    },
    Setting {
        key: "table.topics",
        kind: Kind::Bool,
        default: "off",
        summary: "Whether the table changes topics by poll; off works on the objective it was sent.",
        gate: Some("RT-G07"),
        apply: |c, v| c.topics = v.as_bool(),
    },
    Setting {
        key: "limits.reply",
        kind: Kind::CountOrOff { min: 1, max: MANY },
        default: "off",
        summary: "The most characters a message may have; a longer message is blocked, never cut. Off for no limit.",
        gate: Some("RT-G02"),
        apply: |c, v| c.base_allowance = count(v),
    },
    Setting {
        key: "limits.recovery",
        kind: Kind::Count { min: 1, max: MANY },
        default: "1024",
        summary: "The limit for an agent's one message after it was skipped while busy, when a reply limit is set.",
        gate: Some("RT-G02"),
        apply: |c, v| c.recovery_allowance = count(v).unwrap_or(1024),
    },
    Setting {
        key: "limits.topic_proposal",
        kind: Kind::CountOrOff { min: 1, max: MANY },
        default: "512",
        summary: "The most characters a topic proposal may have; a longer proposal is blocked, never cut. Off for no limit.",
        gate: Some("RT-G13"),
        apply: |c, v| c.topic_proposal_limit = count(v),
    },
    Setting {
        key: "topics.hold_advance_during_poll",
        kind: Kind::Bool,
        default: "on",
        summary: "Whether an agent's advance is refused while a topic poll is running.",
        gate: Some("RT-G11"),
        apply: |c, v| c.hold_advance_during_poll = v.as_bool(),
    },
    Setting {
        key: "topics.poll_busy_agents",
        kind: Kind::Bool,
        default: "off",
        summary: "Whether a topic poll waits for busy agents to propose; off asks only the agents that are free.",
        gate: Some("RT-G21"),
        apply: |c, v| c.poll_busy_agents = v.as_bool(),
    },
    Setting {
        key: "jev.history_rounds",
        kind: Kind::Count { min: 1, max: 100 },
        default: "4",
        summary: "How many completed rounds of discussion JEV sees with each message, within its token limits.",
        gate: Some("RT-G17"),
        apply: |c, v| c.jev_history_rounds = v.as_count().unwrap_or(4),
    },
    Setting {
        key: "jev.gate_pass",
        kind: Kind::Count { min: 1, max: 99 },
        default: "70",
        summary: "The percentage confidence JEV must give each of JEV's three yes/no gates (contribution, usefulness, relevance) for a message to pass.",
        gate: Some("RT-G01"),
        apply: |c, v| c.gate_pass = v.as_count().unwrap_or(70) as f64 / 100.0,
    },
    Setting {
        key: "permissions.scope",
        kind: Kind::Scope,
        default: "workspace",
        summary: "The folder agents' requests are checked against: workspace, project (the nearest folder above it with .git), or an absolute path.",
        gate: Some("RT-G18"),
        apply: |c, v| {
            c.scope = match v {
                Value::Path(p) => Some(p.clone()),
                Value::Word(w) if w == "project" => Some(project_root(&c.workspace)),
                _ => None,
            }
        },
    },
    permission!("read"),
    permission!("edit"),
    permission!("delete"),
    permission!("move"),
    permission!("search"),
    permission!("execute"),
    permission!("think"),
    permission!("fetch"),
    permission!("other"),
    Setting {
        key: "shutdown.force_stop",
        kind: Kind::Bool,
        default: "on",
        summary: "At the end of a table: on sends SIGTERM to an agent still running 1 second after its input closes, then SIGKILL 2 seconds later; off waits for the agent with no signal.",
        gate: Some("RT-G20"),
        apply: |c, v| c.force_stop = v.as_bool(),
    },
];
