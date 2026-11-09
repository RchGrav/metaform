//! Independent observation of agent harnesses with [AgentSight].
//!
//! ACP tells the host what a harness *reports*. This crate shows what the harness process and
//! its descendants actually *do* — programs started and ended, files opened and changed,
//! network connections, HTTP requests and responses on its TLS connections — so a harness that
//! sends no ACP updates can be told apart as working, waiting on the network, exited, or alive
//! with no observable activity (README §10.2–10.3, design §8).
//!
//! The monitor is an observer only. Nothing here judges, times out, or stops an agent; silence
//! is published as nothing, never as failure.
//!
//! # Use
//!
//! The host knows each harness's process id. [`Monitor::attach`] attaches AgentSight's eBPF
//! probes to that process and its descendants and publishes on the [`bus::Bus`]:
//!
//! - [`MonitorAttached`] once per capture that is live, so "no observations" can be read as
//!   "nothing happened" rather than "nobody was watching";
//! - [`Observation`] for each thing the harness tree did, tagged with the harness's pid and the
//!   optional harness id the host chose (the same string `acp-host` uses for the harness);
//! - [`MonitorUnavailable`] whenever a capture cannot run or stops, stating why.
//!
//! Dropping the [`Monitor`] stops its probes. Nothing is published for a stop the host asked
//! for.
//!
//! # Captures
//!
//! - **Process** ([`Capture::Process`]): AgentSight's `process` probe, seeded with the harness
//!   and every descendant alive at attach time, following new descendants in the kernel. It
//!   reports `exec`/exit and file opens as they happen. File mutations, fd writes and network
//!   operations are aggregated by the probe and flushed every five seconds and at process exit.
//!   This capture is required: if it cannot run, `attach` fails.
//! - **TLS** ([`Capture::Tls`]): AgentSight's `sslsniff` probe on the harness process itself,
//!   parsed into HTTP requests and responses by AgentSight's HTTP parser. When the harness
//!   executable carries its own TLS library (Node, Bun and similar runtimes), the probe is
//!   pinned to that executable. TLS made by *descendant* processes is not captured: `sslsniff`
//!   filters on one pid, and widening it to the session would also capture the host's own
//!   traffic. If this capture cannot run, `attach` still succeeds and publishes
//!   [`MonitorUnavailable`] for it.
//!
//! Request and response bodies, headers and raw TLS data are never put on the bus: they carry
//! prompts, responses and credentials. Observations carry only method, host, path, status and
//! the exchange id that pairs a response with its request. AgentSight's own classifier of
//! "LLM" traffic is private to its crate, so this crate does not label requests as model calls;
//! the host and path show which provider endpoint was called.
//!
//! # Requirements
//!
//! Linux with BPF, BTF and uprobes, and a process running as **root** (effective uid 0).
//! AgentSight's runners start the probes directly only as root; otherwise they re-launch them
//! through `sudo -n`. This crate does not let that happen: escalating privileges implicitly from
//! inside an observer is not its decision to make. Without root, `attach` returns
//! [`MonitorUnavailable`] naming the effective uid and capabilities it found.
//!
//! The `agentsight` cargo feature (on by default) enables real capture. It builds with Cargo
//! alone: `agentsight-capture` ships its probes as prebuilt executables, so no clang, libbpf
//! headers or kernel headers are needed to build. At run time the probes load `libelf`, `libz`
//! and `libzstd`. Without the feature, `attach` reports [`MonitorUnavailable`] saying so.
//!
//! [AgentSight]: https://github.com/eunomia-bpf/agentsight

use std::fmt;

use bus::{Bus, Event};
use serde::Serialize;

#[cfg(feature = "agentsight")]
mod capture;

/// The harness a monitor watches, as the host identifies it.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Harness {
    /// Process id of the harness the host launched.
    pub pid: u32,
    /// The host's name for the harness, if it has one (for `acp-host`, its `HarnessId`).
    pub id: Option<String>,
}

impl Harness {
    pub fn new(pid: u32, id: Option<String>) -> Self {
        Self { pid, id }
    }
}

/// One of the monitor's capture mechanisms.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Capture {
    /// Process tree, filesystem and network operations (AgentSight `process` probe).
    Process,
    /// HTTP over TLS made by the harness process (AgentSight `sslsniff` probe).
    Tls,
}

/// A capture is live for a harness: from here on, no observations means no observed activity.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct MonitorAttached {
    pub harness: Harness,
    pub capture: Capture,
}

impl Event for MonitorAttached {
    const NAME: &'static str = "monitor.attached";
}

/// Monitoring of a harness cannot run, or has stopped, and why.
///
/// `capture` is `None` when the whole monitor is unavailable, `Some` when one capture could not
/// start or ended on its own. This says nothing about the agent itself.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct MonitorUnavailable {
    pub harness: Harness,
    pub capture: Option<Capture>,
    pub reason: String,
}

impl Event for MonitorUnavailable {
    const NAME: &'static str = "monitor.unavailable";
}

impl fmt::Display for MonitorUnavailable {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let what = match self.capture {
            None => "monitoring",
            Some(Capture::Process) => "process capture",
            Some(Capture::Tls) => "TLS capture",
        };
        write!(f, "{what} of harness pid {}", self.harness.pid)?;
        if let Some(id) = &self.harness.id {
            write!(f, " ({id})")?;
        }
        write!(f, " is unavailable: {}", self.reason)
    }
}

impl std::error::Error for MonitorUnavailable {}

/// Something a process in the harness's tree was observed doing.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Observation {
    /// The harness whose process tree this came from.
    pub harness: Harness,
    /// The process that did it: the harness or one of its descendants. `None` when the probe
    /// could not attribute it to a process (for example, a count of lost events).
    pub pid: Option<u32>,
    /// That process's command name as the kernel reports it.
    pub comm: String,
    /// When the probe saw it, in milliseconds since the Unix epoch.
    pub observed_at_ms: u64,
    pub activity: Activity,
}

impl Event for Observation {
    const NAME: &'static str = "monitor.observation";
}

/// What was observed. Operation names (`op`) are AgentSight's own, for example `FILE_DELETE`,
/// `FILE_RENAME`, `DIR_CREATE`, `NET_CONNECT`, `NET_BIND`.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum Activity {
    /// A process started a program (`exec`): a tool or subprocess run by the harness, or the
    /// harness itself.
    ProcessSpawn { ppid: Option<u32>, executable: Option<String>, command: Option<String> },
    /// A process ended. When `pid` is the harness's own pid, the harness has exited.
    ProcessExit { ppid: Option<u32>, exit_code: Option<u32>, duration_ms: Option<u64> },
    /// A file was opened. `count` is how many identical opens the probe folded into this one.
    FileOpen { path: String, write: bool, count: u64 },
    /// A file or directory was created, deleted, renamed or truncated (aggregated by the probe).
    FileChange { op: String, path: String, count: u64 },
    /// Writes to one file descriptor (aggregated by the probe). `target` is AgentSight's
    /// description of it, such as `fd=1`.
    Write { target: String, bytes: u64, count: u64 },
    /// Network operations on one target (aggregated by the probe). `target` is `address:port`
    /// when the probe resolved it, otherwise its description such as `family=1`.
    Network { op: String, target: String, count: u64 },
    /// An HTTP request sent over TLS.
    HttpRequest {
        method: Option<String>,
        host: Option<String>,
        path: Option<String>,
        exchange: Option<String>,
    },
    /// An HTTP response received over TLS. `exchange` matches the request's.
    HttpResponse { status: Option<u16>, exchange: Option<String> },
    /// AgentSight's HTTP parser closed out an exchange or a connection without a complete
    /// message: for example the connection closed while a response was still arriving, or the
    /// client stopped reading it. `completion` is AgentSight's completion reason (`partial`,
    /// `closed`, `capture_end`, ...), `direction` the half that was incomplete when known.
    HttpUnfinished { exchange: Option<String>, direction: Option<String>, completion: Option<String> },
    /// The probe dropped `count` events of kind `what` under load.
    EventsLost { what: String, count: u64 },
    /// A record this crate does not map, passed on by its AgentSight source and record name so
    /// that nothing is dropped silently.
    Other { source: String, record: String, detail: Option<String> },
}

/// Independent observation of one harness. Dropping it stops the probes.
pub struct Monitor {
    harness: Harness,
    #[cfg(feature = "agentsight")]
    _running: capture::Running,
}

impl Monitor {
    /// Attach to `harness.pid` and its descendants and publish what they do on `bus`.
    ///
    /// Resolves once the process probe reports that it is attached in the kernel, so
    /// observations start with no gap after this returns. On failure the returned
    /// [`MonitorUnavailable`] has also been published. Must be called within a tokio runtime.
    pub async fn attach(bus: &Bus, harness: Harness) -> Result<Monitor, MonitorUnavailable> {
        #[cfg(feature = "agentsight")]
        {
            let running = capture::attach(bus, &harness).await?;
            Ok(Monitor { harness, _running: running })
        }
        #[cfg(not(feature = "agentsight"))]
        {
            Err(unavailable(
                bus,
                &harness,
                None,
                "agent-monitor was built without its `agentsight` feature, so it has no capture"
                    .to_string(),
            ))
        }
    }

    pub fn harness(&self) -> &Harness {
        &self.harness
    }
}

/// Publish that monitoring is unavailable and return the same event.
fn unavailable(bus: &Bus, harness: &Harness, capture: Option<Capture>, reason: String) -> MonitorUnavailable {
    let event = MonitorUnavailable { harness: harness.clone(), capture, reason };
    bus.publish(event.clone());
    event
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn unavailable_reads_as_a_sentence() {
        let event = MonitorUnavailable {
            harness: Harness::new(42, Some("claude".into())),
            capture: Some(Capture::Tls),
            reason: "no TLS library found".into(),
        };
        assert_eq!(
            event.to_string(),
            "TLS capture of harness pid 42 (claude) is unavailable: no TLS library found"
        );
    }

    #[test]
    fn events_serialize_with_tagged_activity() {
        let observation = Observation {
            harness: Harness::new(7, None),
            pid: Some(8),
            comm: "bash".into(),
            observed_at_ms: 1,
            activity: Activity::ProcessExit { ppid: Some(7), exit_code: Some(0), duration_ms: Some(3) },
        };
        let json = serde_json::to_value(&observation).unwrap();
        assert_eq!(json["activity"]["kind"], "process_exit");
        assert_eq!(json["harness"]["pid"], 7);
        assert_eq!(json["harness"]["id"], serde_json::Value::Null);
    }

    #[cfg(not(feature = "agentsight"))]
    #[test]
    fn without_the_feature_attach_reports_why() {
        let bus = Bus::new();
        let mut events = bus.subscribe::<MonitorUnavailable>();
        let error = futures::executor::block_on(Monitor::attach(&bus, Harness::new(1, None)))
            .err()
            .expect("no capture without the feature");
        assert!(error.reason.contains("`agentsight` feature"));
        let published = futures::executor::block_on(events.recv()).unwrap();
        assert_eq!(*published.event, error);
    }
}
