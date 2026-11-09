//! Answering agents' permission requests without waiting on a person.

use std::collections::BTreeMap;
use std::path::{Component, Path, PathBuf};

use serde::{Deserialize, Serialize};

/// What the agent asked to do, in the terms a policy needs.
#[derive(Debug, Clone)]
pub struct PermissionAsk {
    pub title: Option<String>,
    /// ACP tool kind: read, edit, delete, move, search, execute, think, fetch, other.
    pub kind: Option<String>,
    /// Paths the tool call names. Relative paths are relative to the session's cwd.
    pub locations: Vec<PathBuf>,
    pub cwd: PathBuf,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Verdict {
    Allow { reason: String },
    Reject { reason: String },
}

/// Decides permission requests. Must answer at once: an agent waiting on it is stalled.
pub trait PermissionPolicy: Send + Sync {
    fn decide(&self, ask: &PermissionAsk) -> Verdict;
}

/// Allow everything. For trusted, sandboxed use only.
pub struct AllowAll;

impl PermissionPolicy for AllowAll {
    fn decide(&self, _ask: &PermissionAsk) -> Verdict {
        Verdict::Allow { reason: "policy allows everything".into() }
    }
}

/// How one kind of permission request is answered.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Rule {
    /// Allowed when every path it names is inside the scope; refused otherwise.
    Inside,
    /// Always allowed.
    Allow,
    /// Always refused.
    Refuse,
}

/// The ACP tool kinds a rule can name. A request with no kind, or a kind not listed here,
/// is answered by the rule for `other`.
pub const KINDS: [&str; 9] = ["read", "edit", "delete", "move", "search", "execute", "think", "fetch", "other"];

/// A rule for each kind of request. A kind with no rule is answered `Inside`.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct PermissionRules(pub BTreeMap<String, Rule>);

impl PermissionRules {
    /// The rule for a request of this ACP tool kind.
    pub fn rule(&self, kind: Option<&str>) -> Rule {
        let kind = kind.filter(|k| KINDS.contains(k)).unwrap_or("other");
        self.0.get(kind).copied().unwrap_or(Rule::Inside)
    }
}

/// Answer each request by the rule for its kind (see [`PermissionRules`]). With the default
/// rules, anything whose named paths all lie inside `root` is allowed and anything naming a
/// path outside it is refused; commands are allowed on the same terms, because building and
/// testing software needs them.
///
/// Limit: this checks the paths a request names. It cannot confine what an allowed shell
/// command does once it runs; use a harness sandbox mode for that where one exists.
pub struct ScopePolicy {
    root: PathBuf,
    rules: PermissionRules,
}

impl ScopePolicy {
    pub fn new(root: impl Into<PathBuf>) -> Self {
        Self::with_rules(root, PermissionRules::default())
    }

    pub fn with_rules(root: impl Into<PathBuf>, rules: PermissionRules) -> Self {
        let root = root.into();
        let root = root.canonicalize().unwrap_or(root);
        Self { root, rules }
    }

    pub fn root(&self) -> &Path {
        &self.root
    }

    /// Whether `path` (relative to `cwd`) resolves inside the root. See [`resolve`].
    fn inside(&self, path: &Path, cwd: &Path) -> bool {
        if !path.is_absolute() && !cwd.is_absolute() {
            return false; // no known working directory: refuse rather than guess
        }
        let joined = if path.is_absolute() { path.to_path_buf() } else { cwd.join(path) };
        resolve(joined).is_some_and(|full| full.starts_with(&self.root))
    }
}

/// Linux's limit on symlinks followed while resolving one path (`MAXSYMLINKS`); following
/// dangling links by hand stops where the kernel would report `ELOOP`.
const MAX_SYMLINKS: usize = 40;

/// Where `path` (absolute) would land if written: symlinks are resolved through the deepest
/// existing ancestor, so a new file below an in-scope symlink that points outside is outside.
/// A component that exists only as a dangling symlink is followed to its target rather than
/// treated as a new in-place name, since writing through it creates the target. `..` or `.`
/// in the part that does not exist yet, and any resolution error other than "not found",
/// give `None` (refused).
///
/// The answer describes the filesystem when asked; it cannot stop a later swap of a path
/// component before the agent writes. Harness OS sandboxes are the layer for that.
fn resolve(path: PathBuf) -> Option<PathBuf> {
    let mut target = path;
    'follow: for _ in 0..=MAX_SYMLINKS {
        let mut existing = target.as_path();
        let mut rest: Vec<&std::ffi::OsStr> = Vec::new();
        let resolved = loop {
            match existing.canonicalize() {
                Ok(real) => break real,
                Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
                    if existing.symlink_metadata().is_ok_and(|meta| meta.file_type().is_symlink()) {
                        let link = std::fs::read_link(existing).ok()?;
                        let mut next = if link.is_absolute() { link } else { existing.parent()?.join(link) };
                        for name in rest.iter().rev() {
                            next.push(name);
                        }
                        target = next;
                        continue 'follow;
                    }
                    match (existing.parent(), existing.file_name()) {
                        (Some(parent), Some(name)) => {
                            rest.push(name);
                            existing = parent;
                        }
                        // `..` or the filesystem root that cannot be resolved.
                        _ => return None,
                    }
                }
                Err(_) => return None,
            }
        };
        if target.components().skip(existing.components().count()).any(|c| matches!(c, Component::ParentDir | Component::CurDir)) {
            return None;
        }
        let mut full = resolved;
        for name in rest.into_iter().rev() {
            full.push(name);
        }
        return Some(full);
    }
    None
}

impl PermissionPolicy for ScopePolicy {
    fn decide(&self, ask: &PermissionAsk) -> Verdict {
        let kind = ask.kind.as_deref().unwrap_or("other");
        match self.rules.rule(ask.kind.as_deref()) {
            Rule::Allow => return Verdict::Allow { reason: format!("the table's settings allow {kind} requests") },
            // gate: RT-G18 the table's settings refuse this kind of request
            Rule::Refuse => return Verdict::Reject { reason: format!("the table's settings refuse {kind} requests") },
            Rule::Inside => {}
        }
        let outside: Vec<String> = ask
            .locations
            .iter()
            .filter(|path| !self.inside(path, &ask.cwd))
            .map(|path| path.display().to_string())
            .collect();
        // gate: RT-G18 permission requests naming a path outside the workspace are refused
        if outside.is_empty() {
            Verdict::Allow { reason: format!("inside {}", self.root.display()) }
        } else {
            // gate: RT-G18 the request names a path outside the workspace
            Verdict::Reject {
                reason: format!("outside {}: {}", self.root.display(), outside.join(", ")),
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ask(cwd: &Path, paths: &[&str]) -> PermissionAsk {
        PermissionAsk {
            title: None,
            kind: Some("edit".into()),
            locations: paths.iter().map(PathBuf::from).collect(),
            cwd: cwd.to_path_buf(),
        }
    }

    #[test]
    fn scope_allows_inside_and_rejects_escapes() {
        let root = std::env::temp_dir().join("acp-host-scope-test");
        std::fs::create_dir_all(root.join("work")).unwrap();
        let policy = ScopePolicy::new(&root);
        let cwd = policy.root().join("work");

        assert!(matches!(policy.decide(&ask(&cwd, &["notes.md", "../spec.md"])), Verdict::Allow { .. }));
        assert!(matches!(policy.decide(&ask(&cwd, &[])), Verdict::Allow { .. }));
        assert!(matches!(policy.decide(&ask(&cwd, &["../../etc/passwd"])), Verdict::Reject { .. }));
        assert!(matches!(policy.decide(&ask(&cwd, &["/etc/passwd"])), Verdict::Reject { .. }));
        // A new file deep below a not-yet-existing folder is still checked.
        assert!(matches!(policy.decide(&ask(&cwd, &["new/deeper/file.md"])), Verdict::Allow { .. }));
        // No working directory: relative paths cannot be placed, so they are refused.
        assert!(matches!(policy.decide(&ask(Path::new(""), &["notes.md"])), Verdict::Reject { .. }));
    }

    #[cfg(unix)]
    #[test]
    fn scope_rejects_escapes_through_symlinks() {
        let root = std::env::temp_dir().join("acp-host-scope-symlink");
        let outside = std::env::temp_dir().join("acp-host-scope-outside");
        std::fs::create_dir_all(&root).unwrap();
        std::fs::create_dir_all(&outside).unwrap();
        let link = root.join("link");
        let _ = std::fs::remove_file(&link);
        std::os::unix::fs::symlink(&outside, &link).unwrap();
        let policy = ScopePolicy::new(&root);
        let cwd = policy.root().to_path_buf();
        // A new file through the link lands outside: rejected.
        assert!(matches!(policy.decide(&ask(&cwd, &["link/new-file"])), Verdict::Reject { .. }));
        assert!(matches!(policy.decide(&ask(&cwd, &["link/a/b/c"])), Verdict::Reject { .. }));
        // `..` inside a path that does not exist yet is refused.
        assert!(matches!(policy.decide(&ask(&cwd, &["missing/../../x"])), Verdict::Reject { .. }));
    }

    // Review round 2, F02: a dangling link to a missing file outside the root used to pass,
    // because the guard rebuilt an in-root path from the link's parent.
    #[cfg(unix)]
    #[test]
    fn scope_follows_dangling_symlinks() {
        let base = std::env::temp_dir().join(format!("acp-host-scope-dangling-{}", std::process::id()));
        let root = base.join("root");
        let outside = base.join("outside");
        std::fs::create_dir_all(&root).unwrap();
        std::fs::create_dir_all(&outside).unwrap();
        let link = |name: &str, target: &Path| std::os::unix::fs::symlink(target, root.join(name)).unwrap();
        link("escape", &outside.join("missing.txt"));
        link("escape-dir", &outside.join("no-such-dir"));
        link("hop", &root.join("escape"));
        link("relative", Path::new("../outside/missing.txt"));
        link("inside", &root.join("not-yet.txt"));
        std::fs::write(root.join("present.txt"), "x").unwrap();
        link("present-link", &root.join("present.txt"));
        link("loop-a", &root.join("loop-b"));
        link("loop-b", &root.join("loop-a"));
        let policy = ScopePolicy::new(&root);
        let cwd = policy.root().to_path_buf();
        let rejected = |path: &str| matches!(policy.decide(&ask(&cwd, &[path])), Verdict::Reject { .. });
        for path in ["escape", "escape-dir/new.txt", "hop", "relative", "loop-a"] {
            assert!(rejected(path), "{path} should be refused");
        }
        for path in ["inside", "present-link", "present.txt", "brand-new.txt", "new-dir/new.txt"] {
            assert!(!rejected(path), "{path} should be allowed");
        }
        std::fs::remove_dir_all(&base).unwrap();
    }

    #[test]
    fn each_kind_follows_its_rule() {
        let root = std::env::temp_dir().join("acp-host-scope-rules");
        std::fs::create_dir_all(&root).unwrap();
        let rules = PermissionRules([("execute".to_string(), Rule::Refuse), ("fetch".to_string(), Rule::Allow)].into_iter().collect());
        let policy = ScopePolicy::with_rules(&root, rules);
        let cwd = policy.root().to_path_buf();
        let of = |kind: Option<&str>, paths: &[&str]| PermissionAsk { kind: kind.map(str::to_string), ..ask(&cwd, paths) };

        // Refuse: even a command that names nothing outside is refused, with the reason.
        let refused = policy.decide(&of(Some("execute"), &["build.sh"]));
        assert_eq!(refused, Verdict::Reject { reason: "the table's settings refuse execute requests".into() });
        // Allow: a path outside the scope is allowed.
        assert!(matches!(policy.decide(&of(Some("fetch"), &["/etc/hosts"])), Verdict::Allow { .. }));
        // No rule: inside the scope only. An unknown or missing kind is answered as "other".
        assert!(matches!(policy.decide(&of(Some("edit"), &["/etc/hosts"])), Verdict::Reject { .. }));
        assert!(matches!(policy.decide(&of(Some("switch_mode"), &["notes.md"])), Verdict::Allow { .. }));
        assert!(matches!(policy.decide(&of(None, &["/etc/hosts"])), Verdict::Reject { .. }));
    }
}
