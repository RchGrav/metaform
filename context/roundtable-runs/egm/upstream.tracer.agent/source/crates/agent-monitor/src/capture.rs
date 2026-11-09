//! Capture through `agentsight-capture` and mapping of its records to bus events.

use std::sync::{Arc, Mutex};

use agentsight_capture::analyzers::{Analyzer, HTTPParser, TimestampNormalizer};
use agentsight_capture::binary_resolver::binary_embeds_ssl;
use agentsight_capture::runners::common::runner_error_from_event;
use agentsight_capture::runners::{BinaryRunner, ProcessRunner};
use agentsight_capture::sources::proc::ProcSnapshot;
use agentsight_capture::{BinaryExtractor, EventStream, Runner};
use bus::Bus;
use futures::StreamExt;
use serde_json::Value;
use tokio::task::JoinHandle;

use crate::{Activity, Capture, Harness, MonitorAttached, MonitorUnavailable, Observation, unavailable};

/// A raw AgentSight record.
type Record = agentsight_capture::Event;

/// Live captures of one harness. Dropping it ends the pump tasks, which drops their streams;
/// AgentSight then terminates each probe's process group.
pub(crate) struct Running {
    pumps: Vec<JoinHandle<()>>,
    /// Holds the extracted probe executables for as long as the probes run.
    _probes: BinaryExtractor,
}

impl Drop for Running {
    fn drop(&mut self) {
        for pump in &self.pumps {
            pump.abort();
        }
    }
}

pub(crate) async fn attach(bus: &Bus, harness: &Harness) -> Result<Running, MonitorUnavailable> {
    let fail = |capture, reason| unavailable(bus, harness, capture, reason);

    if let Some(reason) = missing_privileges() {
        return Err(fail(None, reason));
    }
    let snapshot = ProcSnapshot::collect()
        .map_err(|error| fail(None, format!("could not read the process table: {error}")))?;
    // The harness and every descendant alive now; the probe follows later descendants itself.
    let seeds = snapshot.seeds_for_pid_family(harness.pid);
    if seeds.is_empty() {
        return Err(fail(None, format!("harness process {} is not running", harness.pid)));
    }
    let probes = BinaryExtractor::new()
        .await
        .map_err(|error| fail(None, format!("could not extract AgentSight's probe programs: {error}")))?;

    let pid = harness.pid.to_string();
    let mut process = ProcessRunner::from_binary_extractor(probes.get_process_path())
        // Mode 2: report only the tracked (seeded and descendant) processes.
        .with_args(["-p", pid.as_str(), "-m", "2", "--trace-fs", "--trace-net"])
        .with_seed_pids(&seeds);
    let process_error = ErrorSlot::default();
    let stream = process
        .run()
        .await
        .map_err(|error| fail(Some(Capture::Process), format!("the process probe did not start: {error}")))?;
    let mut stream = normalized(process_error.watch(stream)).await.map_err(|error| fail(Some(Capture::Process), error))?;

    // The probe prints its clock anchor once its programs are attached in the kernel; until
    // then nothing is being observed.
    let mut early = Vec::new();
    loop {
        match stream.next().await {
            Some(record) if is_attach_anchor(&record) => break,
            Some(record) => early.push(record),
            None => {
                let reason = process_error.take().unwrap_or_else(|| "its output ended".to_string());
                return Err(fail(
                    Some(Capture::Process),
                    format!("the process probe stopped before it attached: {reason}"),
                ));
            }
        }
    }
    bus.publish(MonitorAttached { harness: harness.clone(), capture: Capture::Process });
    for record in &early {
        if let Some(observation) = observe(harness, record) {
            bus.publish(observation);
        }
    }
    let mut pumps = vec![tokio::spawn(pump(bus.clone(), harness.clone(), Capture::Process, stream, process_error))];

    match start_tls(&probes, harness).await {
        Ok((stream, errors)) => {
            bus.publish(MonitorAttached { harness: harness.clone(), capture: Capture::Tls });
            pumps.push(tokio::spawn(pump(bus.clone(), harness.clone(), Capture::Tls, stream, errors)));
        }
        Err(reason) => {
            fail(Some(Capture::Tls), reason);
        }
    }

    Ok(Running { pumps, _probes: probes })
}

async fn start_tls(probes: &BinaryExtractor, harness: &Harness) -> Result<(EventStream, ErrorSlot), String> {
    let pid = harness.pid.to_string();
    let mut args = vec!["-p".to_string(), pid];
    // Runtimes such as Node and Bun link their own TLS library, which the probe does not find
    // through the system libssl; pin it to the harness executable in that case.
    if let Ok(exe) = std::fs::read_link(format!("/proc/{}/exe", harness.pid)) {
        let exe = exe.to_string_lossy().into_owned();
        if binary_embeds_ssl(&exe) {
            args.extend(["--binary-path".to_string(), exe]);
        }
    }
    let mut runner = BinaryRunner::ssl(probes.get_sslsniff_path()).with_args(&args);
    let stream = runner.run().await.map_err(|error| format!("the TLS probe did not start: {error}"))?;
    let errors = ErrorSlot::default();
    let stream = normalized(errors.watch(stream)).await?;
    // Bodies are parsed but never published; raw data is not even kept.
    let stream = HTTPParser::new()
        .disable_raw_data()
        .process(stream)
        .await
        .map_err(|error| format!("AgentSight's HTTP parser did not start: {error}"))?;
    Ok((stream, errors))
}

/// Timestamps from boot-relative nanoseconds to Unix-epoch milliseconds.
async fn normalized(stream: EventStream) -> Result<EventStream, String> {
    TimestampNormalizer::new()
        .process(stream)
        .await
        .map_err(|error| format!("AgentSight's timestamp normalizer did not start: {error}"))
}

/// Publish every record of one capture until its probe stops, then say that it stopped.
async fn pump(bus: Bus, harness: Harness, capture: Capture, mut stream: EventStream, errors: ErrorSlot) {
    while let Some(record) = stream.next().await {
        if let Some(observation) = observe(&harness, &record) {
            bus.publish(observation);
        }
    }
    let reason = match errors.take() {
        Some(error) => format!("the probe stopped: {error}"),
        None => "the probe's output ended".to_string(),
    };
    bus.publish(MonitorUnavailable { harness, capture: Some(capture), reason });
}

/// The probe's own failure report, taken from its stream before any analyzer can absorb it.
#[derive(Clone, Default)]
struct ErrorSlot(Arc<Mutex<Option<String>>>);

impl ErrorSlot {
    fn watch(&self, stream: EventStream) -> EventStream {
        let slot = self.clone();
        Box::pin(stream.inspect(move |record| {
            if let Some(error) = runner_error_from_event(record) {
                *slot.0.lock().unwrap_or_else(|poisoned| poisoned.into_inner()) = Some(error.to_string());
            }
        }))
    }

    fn take(&self) -> Option<String> {
        self.0.lock().unwrap_or_else(|poisoned| poisoned.into_inner()).take()
    }
}

/// Why this process cannot run AgentSight's probes without escalating, or `None` if it can.
fn missing_privileges() -> Option<String> {
    if !cfg!(target_os = "linux") {
        return Some("AgentSight's eBPF capture runs on Linux only".to_string());
    }
    match std::fs::read_to_string("/proc/self/status") {
        Ok(status) => privilege_shortfall(&status),
        Err(error) => Some(format!("could not read /proc/self/status to check privileges: {error}")),
    }
}

/// Judge a `/proc/<pid>/status` text: AgentSight runs its probes directly only at effective
/// uid 0, and through `sudo -n` otherwise, which this crate does not allow.
fn privilege_shortfall(status: &str) -> Option<String> {
    let field = |name: &str| {
        status.lines().find_map(|line| line.strip_prefix(name)).map(str::split_whitespace)
    };
    let Some(euid) = field("Uid:").and_then(|mut ids| ids.nth(1)).and_then(|id| id.parse::<u32>().ok()) else {
        return Some("could not determine this process's effective uid from /proc/self/status".to_string());
    };
    if euid == 0 {
        return None;
    }
    let caps = field("CapEff:")
        .and_then(|mut value| value.next())
        .and_then(|hex| u64::from_str_radix(hex, 16).ok())
        .unwrap_or(0);
    let held: Vec<&str> = [(39, "CAP_BPF"), (38, "CAP_PERFMON"), (21, "CAP_SYS_ADMIN")]
        .into_iter()
        .filter(|(bit, _)| caps & (1 << bit) != 0)
        .map(|(_, name)| name)
        .collect();
    let held = if held.is_empty() {
        "holds none of CAP_BPF, CAP_PERFMON, CAP_SYS_ADMIN".to_string()
    } else {
        format!("holds {}", held.join(", "))
    };
    Some(format!(
        "eBPF capture needs root: AgentSight starts its probes directly only when this process \
         runs as root (effective uid 0) and otherwise re-launches them through `sudo -n`, which \
         agent-monitor does not allow; this process runs as effective uid {euid} and {held}"
    ))
}

fn is_attach_anchor(record: &Record) -> bool {
    record.data.get("event").and_then(Value::as_str) == Some("CLOCK_SYNC")
        && record.data.get("phase").and_then(Value::as_str) == Some("start")
}

/// Map one AgentSight record to an observation of `harness`. `None` for the probe's own
/// bookkeeping (clock anchors, liveness, its failure report, which is published separately).
pub(crate) fn observe(harness: &Harness, record: &Record) -> Option<Observation> {
    let data = &record.data;
    let text = |key: &str| data.get(key).and_then(Value::as_str).map(str::to_string);
    let number = |key: &str| data.get(key).and_then(Value::as_u64);
    let event = data.get("event").and_then(Value::as_str);
    let kind = data.get("type").and_then(Value::as_str);

    if runner_error_from_event(record).is_some() || matches!(event, Some("CLOCK_SYNC" | "PROBE_LIVENESS")) {
        return None;
    }

    let activity = match (record.source.as_str(), event) {
        ("process", Some("EXEC")) => Activity::ProcessSpawn {
            ppid: number("ppid").map(|v| v as u32),
            executable: text("filename"),
            command: text("full_command"),
        },
        ("process", Some("EXIT")) => Activity::ProcessExit {
            ppid: number("ppid").map(|v| v as u32),
            exit_code: number("exit_code").map(|v| v as u32),
            duration_ms: number("duration_ms"),
        },
        ("process", Some("FILE_OPEN")) => Activity::FileOpen {
            path: text("filepath").unwrap_or_default(),
            write: data.get("write").and_then(Value::as_bool).unwrap_or(false),
            count: number("count").unwrap_or(1),
        },
        ("process", Some(lost)) if lost.ends_with("_LOST") => Activity::EventsLost {
            what: lost.trim_end_matches("_LOST").to_string(),
            count: number("count").unwrap_or(0),
        },
        ("process", Some("SUMMARY")) => {
            let op = kind.unwrap_or_default().to_string();
            let detail = text("detail").unwrap_or_default();
            let count = number("count").unwrap_or(1);
            if op.starts_with("NET_") {
                Activity::Network { op, target: detail, count }
            } else if op.starts_with("FILE_") || op.starts_with("DIR_") {
                // The probe puts the full path in `extra` and its directory in `detail`.
                Activity::FileChange { op, path: text("extra").unwrap_or(detail), count }
            } else if op == "WRITE" {
                Activity::Write { target: detail, bytes: number("total_bytes").unwrap_or(0), count }
            } else {
                Activity::Other { source: record.source.clone(), record: format!("SUMMARY/{op}"), detail: Some(detail) }
            }
        }
        ("http_parser", _) => match text("message_type").as_deref() {
            Some("request") => Activity::HttpRequest {
                method: text("method"),
                host: header(data, "host").or_else(|| header(data, ":authority")),
                path: text("path"),
                exchange: text("http_exchange_id"),
            },
            Some("response") => Activity::HttpResponse {
                status: number("status_code").map(|v| v as u16),
                exchange: text("http_exchange_id"),
            },
            other => Activity::Other {
                source: record.source.clone(),
                record: other.unwrap_or("unknown").to_string(),
                detail: None,
            },
        },
        ("http_correlation", _) => Activity::HttpUnfinished {
            exchange: text("http_exchange_id"),
            direction: text("direction"),
            completion: text("completion_reason"),
        },
        (source, _) => Activity::Other {
            source: source.to_string(),
            // Process records name themselves in `event` or `type`; raw TLS records in `function`.
            record: event.or(kind).or_else(|| data.get("function").and_then(Value::as_str)).unwrap_or("unknown").to_string(),
            detail: text("reason").or_else(|| text("message")).or_else(|| text("detail")),
        },
    };

    Some(Observation {
        harness: harness.clone(),
        pid: (record.pid != 0).then_some(record.pid),
        comm: record.comm.clone(),
        observed_at_ms: record.timestamp,
        activity,
    })
}

/// A header value by case-insensitive name.
fn header(data: &Value, name: &str) -> Option<String> {
    data.get("headers")?
        .as_object()?
        .iter()
        .find(|(key, _)| key.eq_ignore_ascii_case(name))
        .and_then(|(_, value)| value.as_str())
        .map(str::to_string)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn harness() -> Harness {
        Harness::new(6898, Some("seat-1".into()))
    }

    fn record(source: &str, pid: u32, comm: &str, data: Value) -> Record {
        Record::new_with_timestamp(1_793_930_361_000, source.into(), pid, comm.into(), data)
    }

    fn activity(source: &str, pid: u32, data: Value) -> Activity {
        observe(&harness(), &record(source, pid, "x", data)).expect("mapped").activity
    }

    // The records below are verbatim (less unused fields) from AgentSight 1.0.35's probes,
    // captured in a sandbox against a Python harness.

    #[test]
    fn exec_and_exit_become_spawn_and_exit_with_harness_attribution() {
        let exec = record(
            "process",
            6923,
            "bash",
            json!({"timestamp":172716338784u64,"event":"EXEC","comm":"bash","pid":6923,"ppid":6898,
                   "filename":"/usr/bin/bash","full_command":"bash -c ls / >/dev/null"}),
        );
        let observation = observe(&harness(), &exec).unwrap();
        assert_eq!(observation.harness, harness());
        assert_eq!(observation.pid, Some(6923));
        assert_eq!(observation.comm, "bash");
        assert_eq!(observation.observed_at_ms, 1_793_930_361_000);
        assert_eq!(
            observation.activity,
            Activity::ProcessSpawn {
                ppid: Some(6898),
                executable: Some("/usr/bin/bash".into()),
                command: Some("bash -c ls / >/dev/null".into()),
            }
        );

        let exit = json!({"timestamp":172774713915u64,"event":"EXIT","comm":"python3","pid":6898,
                          "ppid":6892,"exit_code":3,"vm_hwm_kb":22656});
        assert_eq!(
            activity("process", 6898, exit),
            Activity::ProcessExit { ppid: Some(6892), exit_code: Some(3), duration_ms: None }
        );
    }

    #[test]
    fn file_records_map_to_open_and_change() {
        let open = json!({"event":"FILE_OPEN","comm":"python3","pid":6898,"count":1,
                          "filepath":"/tmp/am-test.txt","flags":33345,"read":false,"write":true});
        assert_eq!(
            activity("process", 6898, open),
            Activity::FileOpen { path: "/tmp/am-test.txt".into(), write: true, count: 1 }
        );
        let rename = json!({"event":"SUMMARY","comm":"python3","pid":6898,"type":"FILE_RENAME",
                            "detail":"/tmp","count":1,"extra":"/tmp/am-test2.txt"});
        assert_eq!(
            activity("process", 6898, rename),
            Activity::FileChange { op: "FILE_RENAME".into(), path: "/tmp/am-test2.txt".into(), count: 1 }
        );
        let mkdir = json!({"event":"SUMMARY","type":"DIR_CREATE","detail":"/tmp","count":1,"extra":"/tmp/am-dir"});
        assert_eq!(
            activity("process", 6898, mkdir),
            Activity::FileChange { op: "DIR_CREATE".into(), path: "/tmp/am-dir".into(), count: 1 }
        );
        let write = json!({"event":"SUMMARY","type":"WRITE","detail":"fd=3","count":5,"total_bytes":880,"fd":3});
        assert_eq!(activity("process", 6898, write), Activity::Write { target: "fd=3".into(), bytes: 880, count: 5 });
    }

    #[test]
    fn network_summaries_keep_the_probes_target() {
        let connect = json!({"event":"SUMMARY","type":"NET_CONNECT","detail":"104.18.2.115:443","count":1});
        assert_eq!(
            activity("process", 6898, connect),
            Activity::Network { op: "NET_CONNECT".into(), target: "104.18.2.115:443".into(), count: 1 }
        );
        let bind = json!({"event":"SUMMARY","type":"NET_BIND","detail":"family=16","count":1,"port":0});
        assert_eq!(
            activity("process", 6898, bind),
            Activity::Network { op: "NET_BIND".into(), target: "family=16".into(), count: 1 }
        );
    }

    #[test]
    fn http_parser_output_maps_without_bodies_or_headers() {
        let request = json!({"message_type":"request","method":"POST","path":"/api/v1/chat/completions",
                             "headers":{"Host":"openrouter.ai","Authorization":"Bearer secret"},
                             "body":"{\"model\":\"m\"}","http_exchange_id":"x1"});
        let observation = observe(&harness(), &record("http_parser", 6898, "python3", request)).unwrap();
        assert_eq!(
            observation.activity,
            Activity::HttpRequest {
                method: Some("POST".into()),
                host: Some("openrouter.ai".into()),
                path: Some("/api/v1/chat/completions".into()),
                exchange: Some("x1".into()),
            }
        );
        let json = serde_json::to_string(&observation).unwrap();
        assert!(!json.contains("secret") && !json.contains("model"), "{json}");

        let h2 = json!({"message_type":"request","method":"POST","path":"/v1/messages",
                        "headers":{":authority":"api.anthropic.com"}});
        assert!(matches!(
            activity("http_parser", 6898, h2),
            Activity::HttpRequest { host: Some(host), .. } if host == "api.anthropic.com"
        ));

        let response = json!({"message_type":"response","status_code":401,"http_exchange_id":"x1"});
        assert_eq!(
            activity("http_parser", 6898, response),
            Activity::HttpResponse { status: Some(401), exchange: Some("x1".into()) }
        );
    }

    #[test]
    fn unfinished_exchanges_are_reported() {
        // Emitted in the sandbox run when the client stopped reading a chunked 401 response.
        let partial = json!({"connection_id":"c1","connection_generation":0,"protocol":"HTTP/1.1",
                             "direction":"response","correlation_status":"unlinked","completion_reason":"partial",
                             "termination_reason":"closed","buffered_bytes":1150});
        assert_eq!(
            activity("http_correlation", 6898, partial),
            Activity::HttpUnfinished { exchange: None, direction: Some("response".into()), completion: Some("partial".into()) }
        );
        let terminal = json!({"connection_id":"c1","http_exchange_id":"x1","completion_reason":"closed"});
        assert_eq!(
            activity("http_correlation", 6898, terminal),
            Activity::HttpUnfinished { exchange: Some("x1".into()), direction: None, completion: Some("closed".into()) }
        );
        let raw_tls = json!({"function":"READ/RECV","timestamp_ns":1u64,"len":5,"connection_closed":true});
        assert_eq!(
            activity("ssl", 6898, raw_tls),
            Activity::Other { source: "ssl".into(), record: "READ/RECV".into(), detail: None }
        );
    }

    #[test]
    fn probe_bookkeeping_is_not_an_observation() {
        let anchor = record("diagnostic", 0, "process", json!({"event":"CLOCK_SYNC","phase":"start"}));
        assert!(is_attach_anchor(&anchor));
        assert!(observe(&harness(), &anchor).is_none());
        let end = record("diagnostic", 0, "process", json!({"event":"CLOCK_SYNC","phase":"end"}));
        assert!(!is_attach_anchor(&end));
        let failure = record(
            "process",
            0,
            "Process",
            json!({"type":"runner_error","message":"Process exited with exit status: 1"}),
        );
        assert!(observe(&harness(), &failure).is_none());
    }

    #[test]
    fn losses_and_unknown_records_are_published_not_dropped() {
        let lost = record("process", 0, "process", json!({"event":"FILE_OPEN_LOST","pid":0,"count":86}));
        let observation = observe(&harness(), &lost).unwrap();
        assert_eq!(observation.pid, None);
        assert_eq!(observation.activity, Activity::EventsLost { what: "FILE_OPEN".into(), count: 86 });

        let warning = json!({"event":"WARNING","type":"FILE_RATE_LIMIT","message":"Process had 1000+ file ops per second"});
        assert_eq!(
            activity("process", 6898, warning),
            Activity::Other {
                source: "process".into(),
                record: "WARNING".into(),
                detail: Some("Process had 1000+ file ops per second".into()),
            }
        );
        let parse_error = json!({"type":"runner_parse_error","runner":"process","reason":"missing pid"});
        assert_eq!(
            activity("diagnostic", 0, parse_error),
            Activity::Other { source: "diagnostic".into(), record: "runner_parse_error".into(), detail: Some("missing pid".into()) }
        );
    }

    #[test]
    fn privileges_require_effective_root() {
        let root = "Name:\tx\nUid:\t1000\t0\t0\t0\nCapEff:\t000001ffffffffff\n";
        assert_eq!(privilege_shortfall(root), None);

        let user = "Uid:\t1000\t1000\t1000\t1000\nCapEff:\t0000000000000000\n";
        let reason = privilege_shortfall(user).unwrap();
        assert!(reason.contains("effective uid 1000"), "{reason}");
        assert!(reason.contains("holds none of CAP_BPF, CAP_PERFMON, CAP_SYS_ADMIN"), "{reason}");
        assert!(reason.contains("sudo -n"), "{reason}");

        // CAP_BPF (39) and CAP_PERFMON (38) without root: AgentSight would still use sudo.
        let capable = "Uid:\t1000\t1000\t1000\t1000\nCapEff:\t000000c000000000\n";
        let reason = privilege_shortfall(capable).unwrap();
        assert!(reason.contains("holds CAP_BPF, CAP_PERFMON"), "{reason}");
    }

    /// A probe that ends on its own is published as unavailable, with its own failure report.
    #[tokio::test]
    async fn a_probe_that_stops_is_reported_with_its_reason() {
        let records = vec![
            record("process", 6923, "ls", json!({"event":"EXEC","pid":6923,"ppid":6898,"filename":"/usr/bin/ls"})),
            record("process", 0, "Process", json!({"type":"runner_error","message":"Process exited with exit status: 1"})),
        ];
        let errors = ErrorSlot::default();
        let stream = errors.watch(Box::pin(futures::stream::iter(records)));
        let bus = Bus::new();
        let mut observations = bus.subscribe::<Observation>();
        let mut unavailable = bus.subscribe::<MonitorUnavailable>();
        pump(bus.clone(), harness(), Capture::Process, stream, errors).await;

        let spawned = observations.recv().await.unwrap();
        assert!(matches!(spawned.event.activity, Activity::ProcessSpawn { .. }));
        let stopped = unavailable.recv().await.unwrap();
        assert_eq!(
            *stopped.event,
            MonitorUnavailable {
                harness: harness(),
                capture: Some(Capture::Process),
                reason: "the probe stopped: Process exited with exit status: 1".into(),
            }
        );
        assert!(stopped.seq > spawned.seq);
    }

    /// Unprivileged here, attach must refuse with the real reason and publish it.
    #[tokio::test]
    async fn attach_without_root_publishes_the_reason() {
        let status = std::fs::read_to_string("/proc/self/status").unwrap();
        if privilege_shortfall(&status).is_none() {
            eprintln!("running as root; the unprivileged path is not exercised");
            return;
        }
        let bus = Bus::new();
        let mut published = bus.subscribe::<MonitorUnavailable>();
        let harness = Harness::new(std::process::id(), Some("self".into()));
        let error = crate::Monitor::attach(&bus, harness.clone()).await.err().expect("needs root");
        assert_eq!(error.harness, harness);
        assert_eq!(error.capture, None);
        assert!(error.reason.starts_with("eBPF capture needs root"), "{}", error.reason);
        eprintln!("{error}");
        assert_eq!(*published.recv().await.unwrap().event, error);
    }
}
