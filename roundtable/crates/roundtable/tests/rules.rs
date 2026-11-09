use roundtable::rules::*;

#[test]
fn each_turn_starts_with_the_round_count_and_the_last_rounds_count_down() {
    let labels: Vec<String> = (1..=10).map(|r| round_label(r, Some(10))).collect();
    assert_eq!(&labels[..6], &["Round 1 of 10", "Round 2 of 10", "Round 3 of 10", "Round 4 of 10", "Round 5 of 10", "Round 6 of 10"]);
    assert_eq!(&labels[6..], &["3 Rounds Remain", "2 Rounds Remain", "1 Round Remains", "Final Round"]);
    assert_eq!(round_label(1, Some(1)), "Final Round");
    assert_eq!(round_label(12, None), "Round 12", "no limit: the round alone");
}

#[test]
fn truncation_reports_characters_lost_at_grapheme_boundaries() {
    assert_eq!(truncate_to("hello", 5), ("hello", 0));
    assert_eq!(truncate_to("hello world", 5), ("hello", 6));
    assert_eq!(truncate_to("abcde\u{301}f", 5), ("abcd", 3));
}

#[test]
fn replies_are_pass_contribution_or_empty() {
    assert_eq!(classify("PASS"), Reply::Pass);
    assert_eq!(classify(" pass.\n"), Reply::Pass);
    assert_eq!(classify("I pass on that, but no"), Reply::Contribution("I pass on that, but no".into()));
    assert_eq!(classify("WORK\nnotes"), Reply::Contribution("WORK\nnotes".into()), "work is never announced");
    assert_eq!(classify("  "), Reply::Empty);
}

#[test]
fn two_nonproductive_or_two_all_pass_rounds_advance_and_skips_count_as_passes() {
    let mut rounds = RoundTracker::default();
    rounds.record(Outcome::Contributed);
    rounds.record(Outcome::Failed);
    assert!(!rounds.close_round());
    rounds.record(Outcome::Contributed);
    assert!(rounds.close_round(), "two rounds with nothing accepted");

    let mut rounds = RoundTracker::default();
    rounds.record(Outcome::Passed);
    rounds.record(Outcome::Contributed);
    rounds.record_accept();
    assert!(!rounds.close_round());
    rounds.record(Outcome::Passed);
    rounds.record(Outcome::SkippedWorking);
    assert!(!rounds.close_round());
    rounds.record(Outcome::SkippedWorking);
    rounds.record(Outcome::Passed);
    assert!(rounds.close_round(), "two rounds of passes and skips");

    assert!(!RoundTracker::default().close_round(), "an empty round is not a round");
}

#[test]
fn topic_selection_follows_the_readme_example() {
    let proposals: Vec<String> = ["one", "two", "three", "four"].map(String::from).to_vec();
    let table = |i: usize, j: usize| match (i, j) {
        (0, 1) => 0.95,
        (0, 2) => 0.20,
        (0, 3) => 0.15,
        (1, 2) => 0.30,
        (1, 3) => 0.25,
        (2, 3) => 0.85,
        _ => unreachable!(),
    };
    let (winner, totals) = select_topic(&proposals, table).unwrap();
    assert_eq!(winner, "two");
    assert!((totals[1] - 1.50).abs() < 1e-9 && (totals[3] - 1.25).abs() < 1e-9);
    let (tied, _) = select_topic(&proposals[..2], |_, _| 0.5).unwrap();
    assert_eq!(tied, "one and two");
    assert_eq!(select_topic(&proposals[..1], |_, _| 0.0).unwrap().0, "one");
    assert!(select_topic(&[], |_, _| 0.0).is_none());
    assert_eq!(pairs(4).len(), 6);
}

#[test]
fn rating_points_use_the_owners_weights() {
    let full: serde_json::Map<String, serde_json::Value> = serde_json::from_value(serde_json::json!({
        "Efficient": 5, "Alert & Aware": 5, "Thorough": 5, "Coordination": 5, "bonus": true
    })).unwrap();
    assert!((rating_points(&full) - 105.0).abs() < 1e-9);
    let some: serde_json::Map<String, serde_json::Value> = serde_json::from_value(serde_json::json!({"Coordination": 4})).unwrap();
    assert!((rating_points(&some) - 32.0).abs() < 1e-9);
}

/// The rating request is the owner's exact scoring prompt, read from his reference document.
#[test]
fn the_rating_request_is_the_owners_scoring_prompt() {
    let doc = std::fs::read_to_string(concat!(env!("CARGO_MANIFEST_DIR"), "/../../docs/owner-sources/roundtable-agent-ratings.md")).unwrap();
    let start = doc.find("## Exact roundtable scoring prompt").unwrap();
    let body = &doc[start..];
    let open = body.find("```text\n").unwrap() + "```text\n".len();
    let owner = &body[open..open + body[open..].find("\n```").unwrap()];
    // The owner's rubric, from the worker prompt that defined the categories.
    let worker = std::fs::read_to_string(concat!(env!("CARGO_MANIFEST_DIR"), "/../../docs/owner-sources/project_agent.txt")).unwrap();
    let from = worker.find("| Category").unwrap();
    let to = from + worker[from..].find("to the rating.\n").unwrap() + "to the rating.\n".len();
    let rubric = format!("{}\n", &worker[from..to]);
    let owner = owner.replacen("Send your scorecard", &format!("{rubric}Send your scorecard"), 1);
    let expected = owner.replace("<seats/>", "BalmyBoron, NobleChaos");
    assert_eq!(roundtable::prompts::rating_request(&["BalmyBoron".into(), "NobleChaos".into()]), expected);
}

/// Owner's settings design: only what was set is saved, every value shows its source, a bad
/// value is refused with the allowed range, a default comes back on reset, and a saved value
/// that no longer validates is reported and replaced by its default.
#[test]
fn settings_save_only_what_was_set_and_refuse_bad_values() {
    use roundtable::settings::{Source, Store};
    use std::collections::BTreeMap;
    let dir = std::env::temp_dir().join(format!("roundtable-settings-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    let path = dir.join("settings.json");
    let (store, problems) = Store::open(path.clone());
    assert!(problems.is_empty());

    let change = store.set("limits.reply", "1_024").unwrap();
    assert_eq!((change.old.as_str(), change.new.as_str()), ("off", "1024"));
    assert_eq!(store.set("permissions.execute", "REFUSE").unwrap().new, "refuse", "choices are stored in canonical case");
    let refused = store.set("table.rounds", "0").unwrap_err();
    assert!(refused.contains("from 1 to") && refused.contains("or off"), "{refused}");
    assert!(store.set("no.such", "1").is_err());
    let saved: BTreeMap<String, String> = serde_json::from_str(&std::fs::read_to_string(&path).unwrap()).unwrap();
    assert_eq!(saved.len(), 2, "defaults are not stored: {saved:?}");

    let rows = store.list(&BTreeMap::from([("table.rounds".to_string(), "off".to_string())])).unwrap();
    let source = |key: &str| rows.iter().find(|r| r.key == key).map(|r| r.source).unwrap();
    assert_eq!((source("limits.reply"), source("table.rounds"), source("table.topics")), (Source::Saved, Source::Table, Source::Default));

    let mut config = roundtable::TableConfig::new("x", dir.clone(), vec![]);
    store.apply(&mut config, &BTreeMap::from([("table.rounds".to_string(), "off".to_string())])).unwrap();
    assert_eq!((config.base_allowance, config.rounds), (Some(1024), None));
    assert_eq!(config.permissions.rule(Some("execute")), acp_host::Rule::Refuse);
    assert!(store.apply(&mut config, &BTreeMap::from([("table.rondus".to_string(), "3".to_string())])).is_err(), "a misspelt key is refused");

    let reset = store.unset("all").unwrap();
    assert_eq!(reset.len(), 2);
    assert_eq!(store.get("limits.reply").unwrap().1, Source::Default);

    std::fs::write(&path, r#"{"table.rounds": "zero", "jev.gate_pass": "80"}"#).unwrap();
    let (store, problems) = Store::open(path);
    assert_eq!(problems.len(), 1, "{problems:?}");
    assert_eq!(store.get("table.rounds").unwrap().0.text(), "10");
    assert_eq!(store.get("jev.gate_pass").unwrap().0.text(), "80");
}
