# Example Agent Configurations

## Event System Agent - Full Configuration Example

```yaml
agent_name: event_system_analyzer
agent_type: architecture_discovery
phase: 1
parallel_execution: true

system_prompt: |
  You are an Event System Analysis specialist for Python-to-C documentation.
  Your role is to analyze Python codebases and identify all event-driven components,
  creating comprehensive documentation for C reimplementation.

  CRITICAL REQUIREMENTS:
  1. Output MUST be in specified JSON format
  2. All event patterns must have C implementation notes
  3. Skip test files and non-core code
  4. Document thread safety requirements
  5. Identify memory management needs

task_prompt: |
  Analyze the Python codebase in {input_directory} to identify and document all event-driven components.

  INPUT: Python source files from {input_directory}
  
  FOCUS AREAS:
  - Event loops (asyncio, custom implementations)
  - Event handlers and callbacks  
  - Message queues and pub/sub patterns
  - Signal/slot mechanisms
  - Event dispatching logic

  FILE PROCESSING RULES:
  1. SKIP: Files matching patterns:
     - test_*.py, *_test.py, tests/
     - docs/, documentation/
     - build/, dist/, *.egg-info/
     - venv/, env/, __pycache__/
     - setup.py, setup.cfg
  
  2. ANALYZE: All other .py files

  ANALYSIS REQUIREMENTS:
  For each event pattern found:
  1. Identify the pattern type and implementation
  2. Document all handlers and callbacks
  3. Note threading/async context
  4. Propose C implementation approach
  5. Identify memory ownership

  OUTPUT FILES:
  1. {output_dir}/phase1_architecture/event_system_analysis.json
  2. {output_dir}/phase1_architecture/event_system_guide.md

validation_rules:
  - json_schema: event_system_analysis_schema.json
  - required_sections: [event_loops, event_handlers, message_patterns]
  - min_coverage: 95
  - must_have_c_notes: true
```

## Memory Model Agent - Full Configuration Example

```yaml
agent_name: memory_model_designer
agent_type: c_specific_analysis
phase: 3
parallel_execution: true
depends_on: [phase1_complete, phase2_complete]

system_prompt: |
  You are a Memory Model specialist for C implementations.
  Your role is to design comprehensive memory allocation and management strategies
  based on Python codebase analysis.

  CRITICAL REQUIREMENTS:
  1. Every Python object must have a defined C memory strategy
  2. Document ownership for all allocations
  3. Design memory pools for high-frequency allocations
  4. Prevent memory leaks through clear ownership
  5. Consider performance implications

task_prompt: |
  Design memory allocation and management strategies based on analyses from:
  - {output_dir}/phase1_architecture/
  - {output_dir}/phase2_components/

  ANALYSIS TASKS:
  1. Map Python object creation patterns to C allocation strategies
  2. Identify objects suitable for memory pooling
  3. Define ownership rules and transfer mechanisms
  4. Design cleanup strategies replacing Python GC
  5. Document buffer management approaches

  SPECIFIC REQUIREMENTS:
  
  For each allocation pattern:
  - Frequency: Estimate allocation frequency (high/medium/low)
  - Size: Document typical sizes and variations
  - Lifetime: Object lifetime patterns
  - Strategy: Choose stack/heap/pool allocation
  - Ownership: Define clear ownership rules

  For memory pools:
  - Purpose: What objects will use this pool
  - Sizing: Initial size and growth strategy
  - Implementation: Concrete C struct and functions
  - Thread safety: Synchronization needs

  OUTPUT FILES:
  1. {output_dir}/phase3_c_specific/memory_model_analysis.json
  2. {output_dir}/phase3_c_specific/memory_model_guide.md

  VALIDATION REQUIREMENTS:
  - All Python types from previous phases must have memory strategy
  - No allocation without defined ownership
  - Pool designs must include size calculations
  - Thread safety must be explicitly addressed

validation_rules:
  - all_types_covered: true
  - ownership_defined: true
  - pools_have_sizing: true
  - thread_safety_documented: true
```

## Validation Agent - Full Configuration Example

```yaml
agent_name: documentation_validator
agent_type: validation
phase: 4
parallel_execution: false
depends_on: [all_documentation_complete]

system_prompt: |
  You are a Validation specialist ensuring completeness and consistency
  of Python-to-C documentation. Your role is critical for project success.

  CRITICAL REQUIREMENTS:
  1. Verify >95% code coverage or document why not
  2. Ensure all mappings are complete
  3. Identify any gaps or inconsistencies
  4. Validate all cross-references
  5. Confirm implementation feasibility

task_prompt: |
  Validate all generated documentation in {output_dir}

  VALIDATION TASKS:
  
  1. COVERAGE ANALYSIS:
     - Count analyzed vs skipped files
     - Verify skip reasons are valid
     - Calculate coverage percentage
     - List any missed critical files

  2. COMPLETENESS CHECKS:
     - Every Python exception has C error code
     - Every Python type has C equivalent
     - Every algorithm has implementation guide
     - Every interface has C design
     - Every thread/async pattern has C approach

  3. CONSISTENCY VERIFICATION:
     - Cross-reference all phase outputs
     - Identify conflicting recommendations
     - Verify naming conventions
     - Check architectural alignment

  4. GAP IDENTIFICATION:
     - Missing documentation areas
     - Incomplete mappings
     - Unclear implementations
     - Risk areas

  5. IMPLEMENTATION VALIDATION:
     - C code snippets are syntactically valid
     - Memory strategies are complete
     - Error handling is comprehensive
     - Thread safety is addressed

  OUTPUT FILES:
  1. {output_dir}/phase4_synthesis/validation_report.json
  2. {output_dir}/phase4_synthesis/validation_summary.md

  CRITICAL METRICS:
  - Coverage must be >95% or have documented reasons
  - All core components must have guides
  - No high-severity gaps allowed
  - All conflicts must be resolved

validation_rules:
  - min_coverage: 95
  - no_critical_gaps: true
  - all_types_mapped: true
  - no_conflicts: true

output_schema: |
  {
    "coverage": {
      "files_analyzed": "integer",
      "files_skipped": ["list of files"],
      "coverage_percentage": "float",
      "skip_reasons": {"file": "reason"}
    },
    "completeness_checks": {
      "all_exceptions_mapped": "boolean",
      "all_types_mapped": "boolean", 
      "all_algorithms_documented": "boolean",
      "all_interfaces_defined": "boolean",
      "all_threading_mapped": "boolean"
    },
    "consistency_checks": {
      "conflicts": [{"location": "str", "issue": "str", "severity": "str"}],
      "warnings": ["list of warnings"],
      "recommendations": ["list of recommendations"]
    },
    "gaps": [
      {
        "area": "string",
        "description": "string", 
        "severity": "high|medium|low",
        "impact": "string",
        "mitigation": "string"
      }
    ],
    "validation_passed": "boolean"
  }
```

## Agent Orchestration Configuration

```yaml
orchestration:
  execution_model: phased_parallel
  
  phases:
    - phase: 1
      name: architecture_discovery
      parallel: true
      agents: [event_system, platform_abstraction, plugin_system, core_structure, data_flow]
      timeout: 3600
      checkpoint: phase1_complete
      
    - phase: 2  
      name: component_analysis
      parallel: true
      depends_on: phase1_complete
      agents: [routing, state_management, algorithm, interface, resource]
      timeout: 3600
      checkpoint: phase2_complete
      
    - phase: 3
      name: c_specific_analysis  
      parallel: true
      depends_on: [phase1_complete, phase2_complete]
      agents: [memory_model, error_handling, data_structure, threading, performance]
      timeout: 3600
      checkpoint: phase3_complete
      
    - phase: 4
      name: documentation_synthesis
      parallel: false
      depends_on: [phase1_complete, phase2_complete, phase3_complete]
      agents: [architecture_synthesizer, implementation_guide, validation]
      timeout: 7200
      checkpoint: documentation_complete

  error_handling:
    agent_failure: retry_once_then_fail
    phase_failure: stop_execution
    validation_failure: report_and_continue
    
  monitoring:
    progress_updates: true
    checkpoint_saves: true
    detailed_logs: true
```

## Standardized Output Format Examples

### JSON Output Format (event_system_analysis.json)
```json
{
  "metadata": {
    "analysis_timestamp": "2024-01-15T10:30:00Z",
    "agent": "event_system_analyzer",
    "phase": 1,
    "codebase_root": "/path/to/project",
    "files_analyzed": 145,
    "files_skipped": 23
  },
  "event_loops": [
    {
      "name": "main_event_loop",
      "type": "asyncio",
      "location": "src/core/main.py:45",
      "initialization": "asyncio.new_event_loop()",
      "handlers": ["handle_connection", "handle_message", "handle_disconnect"],
      "thread_context": "main_thread",
      "c_implementation_notes": "Use epoll/kqueue for event loop. Handlers as function pointer array."
    }
  ],
  "event_handlers": [
    {
      "name": "handle_connection",
      "event_type": "connection_established", 
      "location": "src/handlers/connection.py:12",
      "async": true,
      "dependencies": ["user_manager", "session_store"],
      "parameters": ["connection_id", "client_info"],
      "c_equivalent": "typedef void (*connection_handler_t)(int conn_id, struct client_info *info);"
    }
  ],
  "message_patterns": {
    "pub_sub": [
      {
        "pattern": "redis_pubsub",
        "channels": ["events", "notifications"],
        "c_implementation": "Custom pub/sub with message queues and epoll"
      }
    ],
    "queues": [],
    "signals": []
  }
}
```

### Markdown Output Format (event_system_guide.md)
```markdown
# Event System Implementation Guide

## Overview
This guide provides a comprehensive mapping of Python event-driven components to C implementations.

## Event Architecture

### Core Event Loop
The Python implementation uses asyncio for the main event loop. The C implementation will use:

```c
// Event loop structure
typedef struct {
    int epoll_fd;           // Linux epoll file descriptor
    int kqueue_fd;          // macOS/BSD kqueue descriptor  
    event_handler_t *handlers;
    size_t handler_count;
    bool running;
} event_loop_t;

// Initialize event loop
event_loop_t* event_loop_create(void);
void event_loop_run(event_loop_t *loop);
void event_loop_stop(event_loop_t *loop);
```

### Event Handlers
Python async handlers map to C function pointers:

| Python Pattern | C Implementation |
|----------------|------------------|
| async def handler() | void (*handler)(event_t*) |
| await async_func() | Callback chain with context |
| asyncio.create_task() | Thread pool task submission |

### Memory Management Considerations
1. Event objects use memory pool allocation
2. Handler contexts are stack-allocated where possible
3. Cleanup through RAII-style cleanup handlers

### Thread Safety Requirements
- Event loop runs on single thread
- Handler registration protected by mutex
- Event queue uses lock-free ring buffer

## Implementation Checklist
- [ ] Design event structure
- [ ] Implement platform-specific event mechanisms
- [ ] Create handler registration system
- [ ] Implement event dispatch
- [ ] Add memory pools for events
- [ ] Create thread safety mechanisms
```

## Inter-Agent Communication Format

```yaml
# Shared context file format
agent_context:
  phase1_discoveries:
    event_patterns: ["asyncio", "custom_events", "signals"]
    platform_requirements: ["linux", "macos", "windows"]
    plugin_interfaces: ["IPlugin", "PluginManager"]
    core_components: ["Router", "StateManager", "EventLoop"]
    
  phase2_analyses:
    routing_type: "dynamic_dispatch"
    state_scope: "global_with_threading"
    key_algorithms: ["path_matching", "message_routing"]
    api_types: ["rest", "websocket", "cli"]
    
  phase3_decisions:
    memory_model: "pools_with_ownership"
    error_strategy: "error_codes_with_context"
    threading_model: "thread_pool_with_async"
    
  critical_paths:
    - "event_dispatch_loop"
    - "message_routing"
    - "state_synchronization"
```
