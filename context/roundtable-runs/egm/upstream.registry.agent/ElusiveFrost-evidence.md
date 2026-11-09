# ElusiveFrost: decisive qualifications

Recommend correcting the description to match the implementation, rather than adding startup caching merely to match stale prose. `autoselect` performs a GET on each invocation (`source/crates/acp-host/src/launch.rs:214-219`); startup callers cannot be ruled out because they are not supplied.

For GF4, distinguish JSON decoding errors from unexpected JSON structure. A request error, unsuccessful HTTP status, or decoding error returns built-ins plus a warning (214-230). Valid JSON with no `agents` array yields zero parsed entries (104-106), then built-ins and no warning (221-228). Thus “all parse failures warn” would mislead operators investigating why registry entries disappeared. Document the silent schema case, or explicitly require schema validation as a separate behavior change.

For GF3, the environment filter runs while constructing local npx/uvx specifications (159-184). The acpr branch instead constructs `acpr <id>` (126-127); acpr's own registry processing is outside this file. The description must not imply universal filtering or inherited-environment cleanup.

For GF8, the supported consequence is lack of protocol-compatibility checking during launch selection. An incompatible agent can therefore be offered, but the host may still negotiate during initialization. With no initialization source supplied, claiming missing registry metadata prevents negotiation goes beyond the evidence.

These corrections are also recorded in the Evidence qualifications section of the shared resolution.md.
