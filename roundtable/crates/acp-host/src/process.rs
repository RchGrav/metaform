//! The harness OS process: start it, watch it, and end it.
//!
//! The process is the leader of its own process group, so ending it also ends what it
//! started (npx -> node -> agent).

use std::collections::VecDeque;
use std::sync::{Arc, Mutex};
use std::time::Duration;

use anyhow::{Context, Result};
use tokio::process::{ChildStdin, ChildStdout};
use tokio::sync::oneshot;

use crate::launch::LaunchSpec;

/// Longest stderr line kept, in bytes; the rest of a longer line is dropped.
const STDERR_LINE_BYTES: usize = 2000;
const STDERR_LINES: usize = 40;

// Shutdown sequence, matching the official ACP SDK's own `AcpAgent` (acp_agent.rs:
// SHUTDOWN_GRACE_PERIOD = 1 s, TERMINATE_GRACE_PERIOD = 2 s): close stdin and wait for the
// agent to exit on its own, then SIGTERM the process group and wait, then SIGKILL the group.
// PENDING OWNER CONFIRMATION: these are the only timers in acp-host; the owner has not yet
// confirmed this sequence. It is the current recommendation.
const EXIT_GRACE: Duration = Duration::from_secs(1);
#[cfg(unix)]
const TERMINATE_GRACE: Duration = Duration::from_secs(2);

/// How the process ended.
pub(crate) struct Exit {
    pub code: Option<i32>,
    pub stderr_tail: String,
    /// Why the ACP connection ended, when it ended with an error.
    pub connection_error: Option<String>,
}

/// A started process, before an ACP connection is put on its pipes.
pub(crate) struct Spawned {
    pub pid: Option<u32>,
    force_stop: bool,
    child: tokio::process::Child,
    tail: Arc<Mutex<VecDeque<String>>>,
    stderr_done: tokio::task::JoinHandle<()>,
}

/// A running process whose ACP connection is up.
pub(crate) struct Process {
    /// Ends the ACP connection. That closes the agent's stdin and starts the shutdown sequence.
    pub stop: oneshot::Sender<()>,
    pub exited: oneshot::Receiver<Exit>,
}

impl Process {
    /// Close the connection and wait for the process to be gone.
    pub async fn end(self) -> Exit {
        let _ = self.stop.send(());
        self.exited.await.unwrap_or(Exit { code: None, stderr_tail: String::new(), connection_error: None })
    }
}

/// Start the process; returns its stdin and stdout for the ACP connection.
pub(crate) fn spawn(spec: &LaunchSpec) -> Result<(ChildStdin, ChildStdout, Spawned)> {
    let mut command = tokio::process::Command::new(&spec.command);
    // Removals apply to what the child would inherit; explicit variables are set afterwards,
    // so a variable both removed and set (a scrubbed secret a seat opts back into) is set.
    for name in &spec.env_remove {
        command.env_remove(name);
    }
    command
        .args(&spec.args)
        .envs(&spec.env)
        .stdin(std::process::Stdio::piped())
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .kill_on_drop(true);
    #[cfg(unix)]
    command.process_group(0);
    let mut child = command.spawn().with_context(|| format!("could not start {}", spec.display()))?;
    let pid = child.id();
    let stdin = child.stdin.take().context("no stdin")?;
    let stdout = child.stdout.take().context("no stdout")?;
    let stderr = child.stderr.take().context("no stderr")?;
    let tail = Arc::new(Mutex::new(VecDeque::new()));
    let stderr_done = tokio::spawn(read_stderr(stderr, tail.clone()));
    Ok((stdin, stdout, Spawned { pid, force_stop: spec.force_stop, child, tail, stderr_done }))
}

impl Spawned {
    /// Watch the process. `connection_ended` fires (with the connection's error, if any) when
    /// the ACP connection over its stdio ends; `stop` must end that connection.
    pub fn supervise(
        self,
        stop: oneshot::Sender<()>,
        connection_ended: oneshot::Receiver<Option<String>>,
    ) -> Process {
        let Spawned { pid, force_stop, mut child, tail, stderr_done } = self;
        let (exited_tx, exited_rx) = oneshot::channel();
        tokio::spawn(async move {
            let mut connection_ended = connection_ended;
            let mut connection_error = None;
            let status = tokio::select! {
                status = child.wait() => status,
                ended = &mut connection_ended => {
                    connection_error = ended.ok().flatten();
                    end_process(pid, force_stop, &mut child).await
                }
            };
            // The leader is gone; end anything it left in its process group.
            #[cfg(unix)]
            if let Some(pid) = pid.filter(|_| force_stop) {
                signal_group(pid, libc::SIGKILL);
            }
            // The whole group is gone, so stderr is closed: the reader finishes on its own.
            let _ = stderr_done.await;
            if connection_error.is_none() {
                // Not a wait: take the connection's error only if it has already ended.
                connection_error = connection_ended.try_recv().ok().flatten();
            }
            let stderr_tail = tail.lock().unwrap().iter().cloned().collect::<Vec<_>>().join("\n");
            let _ = exited_tx.send(Exit {
                code: status.ok().and_then(|status| status.code()),
                stderr_tail,
                connection_error,
            });
        });
        Process { stop, exited: exited_rx }
    }
}

/// The ACP connection has ended, which closed the agent's stdin. With `force_stop`, give the
/// agent the grace period to exit on its own, then SIGTERM the group, then SIGKILL it. Without
/// it, wait for the agent to exit on its own, however long that takes.
async fn end_process(pid: Option<u32>, force_stop: bool, child: &mut tokio::process::Child) -> std::io::Result<std::process::ExitStatus> {
    if !force_stop {
        return child.wait().await;
    }
    // gate: RT-G20 agent processes are killed on a timer at shutdown
    if let Ok(status) = tokio::time::timeout(EXIT_GRACE, child.wait()).await {
        return status;
    }
    #[cfg(unix)]
    if let Some(pid) = pid {
        signal_group(pid, libc::SIGTERM);
        if let Ok(status) = tokio::time::timeout(TERMINATE_GRACE, child.wait()).await {
            return status;
        }
        signal_group(pid, libc::SIGKILL);
    }
    #[cfg(not(unix))]
    let _ = pid;
    let _ = child.start_kill();
    child.wait().await
}

#[cfg(unix)]
fn signal_group(pid: u32, signal: libc::c_int) {
    // The child was started as the leader of its own process group (pgid == pid).
    // SAFETY: killpg only sends a signal; an unknown group returns ESRCH.
    unsafe {
        libc::killpg(pid as libc::pid_t, signal);
    }
}

/// Keep the last lines of stderr, each bounded in length, until the stream closes.
async fn read_stderr(stderr: tokio::process::ChildStderr, tail: Arc<Mutex<VecDeque<String>>>) {
    use tokio::io::AsyncReadExt;
    let mut stderr = stderr;
    let mut buffer = [0u8; 4096];
    let mut line: Vec<u8> = Vec::new();
    let push = |line: &mut Vec<u8>| {
        let mut tail = tail.lock().unwrap();
        if tail.len() == STDERR_LINES {
            tail.pop_front();
        }
        tail.push_back(String::from_utf8_lossy(line).into_owned());
        line.clear();
    };
    while let Ok(read) = stderr.read(&mut buffer).await {
        if read == 0 {
            break;
        }
        for &byte in &buffer[..read] {
            if byte == b'\n' {
                push(&mut line);
            } else if line.len() < STDERR_LINE_BYTES {
                line.push(byte);
            }
        }
    }
    if !line.is_empty() {
        push(&mut line);
    }
}

#[cfg(test)]
mod tests {
    use tokio::io::AsyncReadExt;

    use super::*;

    // A variable scrubbed from the inherited environment and then set explicitly reaches the
    // child (review round 2, F19: an opted-in OpenRouter key was being removed after it was set).
    #[tokio::test]
    async fn explicit_env_wins_over_removal() {
        let mut spec = LaunchSpec::new("sh", ["-c", "printf %s \"${RT_PROCESS_TEST_KEY-unset}\""]);
        spec.env_remove.push("RT_PROCESS_TEST_KEY".into());
        spec.env.insert("RT_PROCESS_TEST_KEY".into(), "shared".into());
        let (_stdin, mut stdout, _spawned): (_, ChildStdout, _) = spawn(&spec).unwrap();
        let mut out = String::new();
        stdout.read_to_string(&mut out).await.unwrap();
        assert_eq!(out, "shared");

        let mut spec = LaunchSpec::new("sh", ["-c", "printf %s \"${HOME-unset}\""]);
        spec.env_remove.push("HOME".into());
        let (_stdin, mut stdout, _spawned): (_, ChildStdout, _) = spawn(&spec).unwrap();
        let mut out = String::new();
        stdout.read_to_string(&mut out).await.unwrap();
        assert_eq!(out, "unset");
    }
}
