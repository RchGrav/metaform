//! Refs are relative to the project folder.
//!
//! A ref is the uri of an artifact: `ref` in a want, and each item of `refs` on an element. A map
//! must still hold when the project folder moves (founder, 2026-11-12), so a ref to a file
//! inside the project is stored as its path from the project folder, not as an absolute path
//! or a `file://` uri. A ref to something outside the project, such as a web address, is kept
//! as written.

use serde_json::{Map as JsonMap, Value, json};

use crate::refusal::{Code, Refusal};

/// The path of `uri` from `folder`, if `uri` is an absolute path or a `file://` uri inside
/// `folder`. The folder itself is `.`. `None` for anything else: a relative path, a web address,
/// or a file outside the project.
fn relative(uri: &str, folder: &str) -> Option<String> {
    let path = uri.strip_prefix("file://").unwrap_or(uri);
    if !path.starts_with('/') {
        return None;
    }
    let folder = folder.trim_end_matches('/');
    let rest = path.strip_prefix(folder)?;
    match rest.trim_end_matches('/') {
        "" => Some(".".to_string()),
        inside if rest.starts_with('/') => Some(inside.trim_start_matches('/').to_string()),
        _ => None,
    }
}

/// One ref made relative if it is inside the folder. Each rewritten ref is added to `changed`,
/// as written and as stored.
fn fix(value: &Value, folder: &str, changed: &mut Vec<(String, String)>) -> Value {
    match value.as_str().and_then(|uri| relative(uri, folder).map(|path| (uri, path))) {
        Some((uri, path)) => {
            changed.push((uri.to_string(), path.clone()));
            json!(path)
        }
        None => value.clone(),
    }
}

/// The fields of one element with each ref made relative.
fn fields(supplied: &JsonMap<String, Value>, folder: &str, changed: &mut Vec<(String, String)>) -> Value {
    let mut out = JsonMap::new();
    for (key, value) in supplied {
        let fixed = match (key.as_str(), value) {
            ("refs", Value::Array(items)) => Value::Array(items.iter().map(|item| fix(item, folder, changed)).collect()),
            ("wants", Value::Array(records)) => Value::Array(
                records
                    .iter()
                    .map(|record| match record {
                        Value::Object(want) => Value::Object(
                            want.iter()
                                .map(|(name, held)| (name.clone(), if name == "ref" { fix(held, folder, changed) } else { held.clone() }))
                                .collect(),
                        ),
                        other => other.clone(),
                    })
                    .collect(),
            ),
            (_, Value::Object(beneath)) => fields(beneath, folder, changed),
            _ => value.clone(),
        };
        out.insert(key.clone(), fixed);
    }
    Value::Object(out)
}

/// Refuse an `add` or `update` that gives a ref inside the project folder as an absolute path or
/// a `file://` uri. The remediation is the same command with each such ref relative to the
/// folder. Any other command passes.
pub fn check_relative(command: &Value, folder: &str) -> Result<(), Refusal> {
    let Some((verb, Value::Object(selected))) = command.as_object().and_then(|object| object.iter().next()) else {
        return Ok(());
    };
    if verb != "add" && verb != "update" {
        return Ok(());
    }
    let mut changed = Vec::new();
    let fixed: JsonMap<String, Value> = selected
        .iter()
        .map(|(address, supplied)| match supplied {
            Value::Object(supplied) => (address.clone(), fields(supplied, folder, &mut changed)),
            other => (address.clone(), other.clone()),
        })
        .collect();
    let Some((written, stored)) = changed.first() else {
        return Ok(());
    };
    Err(Refusal::new(
        Code::FieldMismatch,
        format!("a ref inside the project is its path from the project folder, so the map holds when the folder moves: '{written}' is '{stored}'"),
        Some(json!({verb: fixed})),
    ))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_ref_inside_the_project_is_made_relative_and_others_are_kept() {
        let folder = "/home/a/photos";
        assert_eq!(relative("file:///home/a/photos/02.jpg", folder).as_deref(), Some("02.jpg"));
        assert_eq!(relative("/home/a/photos/sub/02.jpg", folder).as_deref(), Some("sub/02.jpg"));
        assert_eq!(relative("file:///home/a/photos/", folder).as_deref(), Some("."));
        assert_eq!(relative("/home/a/photos-old/02.jpg", folder), None);
        assert_eq!(relative("02.jpg", folder), None);
        assert_eq!(relative("https://example.com/02.jpg", folder), None);
        let command = json!({"add": {"downstream.seller": {
            "refs": ["file:///home/a/photos/"],
            "wants": [{"element": "media.photo.subject", "why": "w", "how": "h", "direction": "receive", "ref": "/home/a/photos/02.jpg"}]
        }}});
        let refusal = check_relative(&command, folder).unwrap_err();
        assert_eq!(
            refusal.remediation.as_deref(),
            Some(&json!({"add": {"downstream.seller": {
                "refs": ["."],
                "wants": [{"element": "media.photo.subject", "why": "w", "how": "h", "direction": "receive", "ref": "02.jpg"}]
            }}}))
        );
        assert!(check_relative(refusal.remediation.as_deref().unwrap(), folder).is_ok());
    }
}
