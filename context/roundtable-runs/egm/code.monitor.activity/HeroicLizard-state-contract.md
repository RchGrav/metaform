# Counterexamples to the original proposed display table

These checks refine the description resolution without changing production code.

1. **Loss is not work.** `capture.rs:246–248` maps a loss count to an `Observation` with `EventsLost`; `capture.rs:473–477` demonstrates a null process PID. Thus “any Observation within a freshness window” would label loss bookkeeping as working. The same rule would label a just-observed harness exit as working. Select positive activity and define precedence instead.
2. **Attachment is historical and per capture.** `capture.rs:82, 92` publish attachment events; `capture.rs:146` later reports stream end for a capture. `capture.rs:29–34` aborts pumps on host-requested Drop, with no stop event. An attachment followed by silence therefore cannot alone establish present coverage or waiting. Waiting also requires a known in-flight request, an input the monitor does not supply.
3. **Capture failure changes confidence.** Losing process coverage need not mean the participant failed, but must affect how silence is interpreted. Ignoring `MonitorUnavailable` entirely leaves an earlier attachment incorrectly treated as current. Track per-capture health, consider independent ACP/lifecycle evidence, and retain unknown when evidence is inadequate.
4. **Process and session attribution differ.** `capture.rs:295–300` always copies the harness tag and maps a zero source PID to `None`. No session field exists. A nonzero process PID still says nothing about which ACP session caused the activity; an `Other` observation can also retain a nonzero PID.

The shared `resolution.md` state table and GF10 text have been corrected accordingly. The table is a proposed consumer model, not an implemented or fully specified contract. Historical responsive/occupied audit terms should remain historical, not be collapsed into five exclusive display states without evidence.
