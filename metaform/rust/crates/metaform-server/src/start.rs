//! Starting a home's server when no server answers: launcher step 5 and SL-6.1 in
//! `context/topogee-repo/docs/designs/service-launcher.md`; D-RS1 in `metaform/docs/designs/metaform-rust.md`.
//!
//! With the project's service launcher installed, the forwarder starts the server as a named,
//! retained user call, so it has a record, captured logs and `hold <name>` to start it again.
//! Without it, the forwarder starts the server itself, detached in its own process group.
//!
//! The launcher is the one `METAFORM_LAUNCHER` names. Empty means no launcher. If the variable is
//! unset, `hold` on `PATH` is used, but only if it is this project's launcher: `hold help system`
//! must name the `topogee/services` store. Another `hold`, such as HoldOn itself, is ignored.
//!
//! User services only: no `sudo`, no `--user`, no `--cap`. The server runs as the user, and its
//! record lands in `~/.local/state/topogee/services/` (SL-5.1, SL-6.1).

use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};

/// How the server was started.
pub enum Started {
    /// Through the launcher, as the call with this name. The launcher has already returned.
    Launcher(String),
    /// Directly, as this child process.
    Direct(Child),
}

/// The launcher to use, if any.
pub fn launcher() -> Option<PathBuf> {
    match std::env::var_os("METAFORM_LAUNCHER") {
        Some(path) if path.is_empty() => None,
        Some(path) => Some(PathBuf::from(path)),
        None => {
            let found = std::env::var_os("PATH")
                .map(|paths| {
                    std::env::split_paths(&paths)
                        .map(|dir| dir.join("hold"))
                        .collect::<Vec<_>>()
                })
                .unwrap_or_default()
                .into_iter()
                .find(|candidate| candidate.is_file())?;
            is_project_launcher(&found).then_some(found)
        }
    }
}

fn is_project_launcher(hold: &Path) -> bool {
    Command::new(hold)
        .args(["help", "system"])
        .stdin(Stdio::null())
        .output()
        .is_ok_and(|out| String::from_utf8_lossy(&out.stdout).contains("topogee/services"))
}

/// The launcher call name for a home: stable, so every forwarder for the home finds the same
/// call. `metaform-` and 12 hex digits of the FNV-1a hash of the home's canonical path. FNV is
/// used because Rust's own hasher may change between releases.
pub fn call_name(home: &Path) -> String {
    let canonical = std::fs::canonicalize(home).unwrap_or_else(|_| home.to_path_buf());
    let mut hash: u64 = 0xcbf2_9ce4_8422_2325;
    for byte in canonical.as_os_str().as_encoded_bytes() {
        hash ^= u64::from(*byte);
        hash = hash.wrapping_mul(0x0000_0100_0000_01b3);
    }
    format!("metaform-{:012x}", hash >> 16)
}

/// Start the home's server: through the launcher if there is one, otherwise directly.
pub fn start(home: &Path, server_exe: &Path) -> Result<Started, String> {
    match launcher() {
        Some(hold) => start_with_launcher(&hold, home, server_exe).map(Started::Launcher),
        None => start_directly(home, server_exe).map(Started::Direct),
    }
}

/// Create the named call. If a call with the name already exists (exit 5, "already exists"),
/// start it again from its recipe by name. A rerun that finds it running (exit 6) is fine: the
/// server is up or starting, and the forwarder's connect loop finds it.
fn start_with_launcher(hold: &Path, home: &Path, server_exe: &Path) -> Result<String, String> {
    let name = call_name(home);
    let created = Command::new(hold)
        .args(["-d", "--name", &name, "--restart", "on-failure:3", "--"])
        .arg(server_exe)
        .arg("serve")
        .arg("--home")
        .arg(home)
        .stdin(Stdio::null())
        .output()
        .map_err(|e| format!("could not run the launcher {}: {e}", hold.display()))?;
    if created.status.success() {
        return Ok(name);
    }
    let why = String::from_utf8_lossy(&created.stderr).to_string();
    if !why.contains("already exists") {
        return Err(format!(
            "the launcher could not start the server: {}",
            why.trim()
        ));
    }
    let rerun = Command::new(hold)
        .arg(&name)
        .stdin(Stdio::null())
        .output()
        .map_err(|e| format!("could not run the launcher {}: {e}", hold.display()))?;
    match rerun.status.code() {
        Some(0) | Some(6) => Ok(name),
        _ => Err(format!(
            "the launcher could not start call {name} again: {}",
            String::from_utf8_lossy(&rerun.stderr).trim()
        )),
    }
}

/// Start the server as a child in its own process group, so it outlives the harness. Its output
/// goes to `<home>/server.log`, appended, because forwarders that start at once share the file.
fn start_directly(home: &Path, server_exe: &Path) -> Result<Child, String> {
    let log = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(home.join("server.log"))
        .map_err(|e| e.to_string())?;
    let mut command = Command::new(server_exe);
    command.arg("serve").arg("--home").arg(home);
    command
        .stdin(Stdio::null())
        .stdout(log.try_clone().map_err(|e| e.to_string())?)
        .stderr(log);
    {
        use std::os::unix::process::CommandExt;
        command.process_group(0);
    }
    command
        .spawn()
        .map_err(|e| format!("could not start {}: {e}", server_exe.display()))
}
