//! Seat environments (review round 2, F01 and F19).

use roundtable::{SECRET_ENV, SeatConfig};

fn seat(share: bool) -> SeatConfig {
    let mut launch = acp_host::LaunchSpec::new("agent", Vec::<String>::new());
    // A seat configuration that tries to pass secrets explicitly gets them removed too.
    launch.env.insert("ROUNDTABLE_TOKEN".into(), "chair-token".into());
    launch.env.insert("TYPESAFE_API_KEY".into(), "typesafe".into());
    launch.env.insert("UNRELATED".into(), "kept".into());
    SeatConfig { name: "Sol".into(), harness: "fake".into(), launch, settings: vec![], share_openrouter_key: share, resume_session: None }
}

#[test]
fn secrets_and_the_chair_token_never_reach_a_seat() {
    let (launch, warning) = seat(false).launch_spec(Some("or-key".into()));
    assert!(warning.is_none());
    for name in SECRET_ENV {
        assert!(launch.env_remove.iter().any(|n| n == name), "{name} must be removed from the inherited environment");
        assert!(!launch.env.contains_key(name), "{name} must not be set explicitly");
    }
    assert_eq!(launch.env.get("UNRELATED").map(String::as_str), Some("kept"));
}

#[test]
fn an_opted_in_seat_gets_only_the_openrouter_key() {
    let (launch, warning) = seat(true).launch_spec(Some("or-key".into()));
    assert!(warning.is_none());
    // acp-host removes inherited variables before setting explicit ones (tested in
    // acp-host's process tests), so the explicit key survives its own removal.
    assert_eq!(launch.env.get("OPENROUTER_API_KEY").map(String::as_str), Some("or-key"));
    assert!(!launch.env.contains_key("ROUNDTABLE_TOKEN"));
    assert!(!launch.env.contains_key("TYPESAFE_API_KEY"));

    let (launch, warning) = seat(true).launch_spec(None);
    assert!(!launch.env.contains_key("OPENROUTER_API_KEY"));
    assert!(warning.is_some_and(|w| w.contains("none is set")));
}

#[test]
fn opencode_seats_route_permissions_to_roundtable_by_default() {
    let env = roundtable::default_env("opencode");
    let (key, value) = &env[0];
    assert_eq!(key, "OPENCODE_CONFIG_CONTENT");
    let config: serde_json::Value = serde_json::from_str(value).unwrap();
    for permission in ["edit", "bash", "webfetch", "external_directory"] {
        assert_eq!(config["permission"][permission], "ask", "{permission}");
    }
    assert!(roundtable::default_env("claude-acp").is_empty());
}
