//! Answering agents' permission requests without waiting on a person.

use std::path::{Component, Path, PathBuf};

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

/// Allow anything whose named paths all lie inside `root`; reject anything naming a path
/// outside it. Commands are allowed, because building and testing software needs them.
///
/// Limit: this checks the paths a request names. It cannot confine what an allowed shell
/// command does once it runs; use a harness sandbox mode for that where one exists.
pub struct ScopePolicy {
    root: PathBuf,
}

impl ScopePolicy {
    pub fn new(root: impl Into<PathBuf>) -> Self {
        let root = root.into();
        let root = root.canonicalize().unwrap_or(root);
        Self { root }
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
}
