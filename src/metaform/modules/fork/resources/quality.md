## Objective

Hone in on the correct plugin shape and implementation structure.

Treat this as a mission-critical engineering effort with aerospace-grade expectations for code quality, reliability, maintainability, and technical discipline.

Design the plugin structure so that the resulting code is:

* clearly organized by responsibility and ownership;
* straightforward to understand, inspect, test, and modify;
* strongly typed where interfaces and state cross boundaries;
* explicit about lifecycle, resource ownership, execution context, and failure behavior;
* reliable across synchronous, asynchronous, event-driven, persistence, unload, reload, and shutdown paths;
* documented at the public and architectural boundaries;
* resistant to hidden coupling, resource leakage, state corruption, concurrency faults, and ambiguous ownership;
* built around small, cohesive components with stable interfaces;
* structured to keep future maintenance cost and technical debt low;
* implemented with the level of care expected when failures are expensive and long-term maintainability matters.

Prefer simple, explicit, durable engineering over cleverness or unnecessary abstraction. Do not add architecture merely for hypothetical future flexibility, but do not accept shortcuts that create fragile lifecycle, concurrency, persistence, or maintenance behavior.

The immediate goal is to determine and implement the **right plugin shape**: a repeatable structure that substantial Metaform modules can follow consistently while remaining clean participants in the chassis contract.
