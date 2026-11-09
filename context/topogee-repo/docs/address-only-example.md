# Address-only example

**Status of this file.** The founder supplied this text on 2026-10-30. It is a demonstration of a mechanism. The lists are generated example content. They are not Metaform rules, and they are not code quality requirements. The preprint says the same thing: "The generated practices remain example content, not requirements imposed on every artifact of the type." (`preprint-v1.0.md` §3.1)

The founder's statement of its purpose: "I was attempting to teach you what a knowledge layer was, how its possible to magnify a propt across the whole functional topology of a project.. those are not our rules that was a demo.."

The text below is unchanged from what the founder supplied.

---

**Reading this example**

The four lists below were generated from nothing but namespace addresses. No repo, no code, and no description of a project were supplied. Each list comes from a single prompt of the form "write 10 best practices for [address]." The address alone was enough to produce useful, distinct guidance, which makes the address itself a prompting surface.

The address can also be taken apart. `code.engine.game.fps` contains four valid addresses: `code`, `code.engine`, `code.engine.game`, and `code.engine.game.fps`. Each prefix is a complete type in its own right and yields its own inference. Running them in order from trunk to leaf produces the progression below. General practice for all code comes first, then practice for engines, then for game engines, then for first-person game engines.

The segments don't contribute equally. The trunk and branch orient the agent: they establish that this is code, and that it is engine code, so the output stays in the right domain. But the content of each list leans heavily on the last segment. The `engine` list is about memory, hardware, and concurrency because of the word "engine." The `fps` list is about aim, input latency, and hit registration because of "fps." The leaf is where the inference comes from, and the rest of the address keeps it from drifting.

Inheritance runs one way. Any practice from a parent applies to its children: "validate all untrusted input" from `code` holds for every engine, every game engine, and every FPS engine. The reverse is never true: "rewind enemy positions to resolve hits" from `fps` means nothing for code in general. This gives two uses. Practices generated at a parent can be attached once and inherited by every artifact beneath it. And a practice that would still hold after its leaf segment is removed belongs higher in the tree, or in a sibling branch, not at the leaf where it was generated.

Notice how little the lists overlap. Where they do repeat each other, the repetition marks a practice that belongs to the parent and was restated by the child.

---

# Code (code)

1. **Maintain Consistent Coding Style**
   * Use uniform indentation, bracket placement, and naming conventions across your team
   * Automate enforcement with tools like Prettier or Black to reduce friction

2. **Use Descriptive Naming**
   * Choose clear, meaningful names for variables, functions, and classes
   * Avoid abbreviations and single letters that require guesswork to understand

3. **Keep Your Code DRY (Don't Repeat Yourself)**
   * Extract repeating logic into reusable functions or modules
   * Each distinct task should live in one place to simplify maintenance

4. **Write Modular Code**
   * Break large files or functions into smaller, independent pieces
   * Each module should handle one specific job well

5. **Handle Errors Gracefully**
   * Anticipate failures and use proper error management like try-catch blocks
   * Prevent applications from crashing unexpectedly by validating inputs early

6. **Use Comments Sparingly and Wisely**
   * Write code that is clean and self-explanatory
   * Reserve comments to explain *why* a complex design choice was made, not *what* the code does

7. **Reduce Global Dependencies**
   * Minimize global variables and pass parameters explicitly to functions
   * This makes code safer, easier to test, and simpler to reason about

8. **Apply Unit Testing**
   * Test individual units of logic to catch bugs early in development
   * Write tests that are stateless and side-effect-free for reliable results

9. **Refactor Continuously**
   * Improve code structure regularly without changing external behavior
   * This reduces technical debt and keeps the codebase healthy over time

10. **Prioritize Security**
    * Validate all user inputs and sanitize untrusted data
    * Keep external libraries up to date to prevent common vulnerabilities

---

# Engine Code (code.engine)

1. **Prioritize Data-Oriented Design**
   * Structure data in memory to match how the CPU fetches it
   * Use contiguous arrays (Structure of Arrays) to minimize cache misses

2. **Zero-Allocation & Strict Memory Management**
   * Avoid standard runtime allocations during execution loops
   * Use arena, stack, or pool allocators for deterministic memory management

3. **Design for Mechanical Sympathy**
   * Write code that works with the underlying hardware, not against it
   * Profile with hardware tools first; never optimize based on intuition alone

4. **Enforce Strict Concurrency and Job Systems**
   * Minimize mutexes and synchronization locks in performance-critical paths
   * Divide engine tasks into small jobs managed by a thread pool

5. **Abstract the Platform, Not the Performance**
   * Create thin abstraction layers for platform-specific hardware
   * Ensure abstractions introduce zero hidden performance costs

6. **Build Comprehensive Telemetry & Profiling Hooks**
   * Embed real-time performance counters and memory trackers from day one
   * Ensure diagnostic features can toggle on and off without altering core timing

7. **Emphasize Determinism and Reproducibility**
   * Decouple internal tick rates from frame rates or incoming data streams
   * Enable engine state to be serialized and deserialized perfectly for debugging and testing

8. **Optimize for Minimal External Dependencies**
   * Limit reliance on massive third-party frameworks
   * Keep internal headers clean with proper forward-declarations for fast compilation

9. **Treat Security and Isolation as Core Features**
   * Isolate untrusted code using lightweight sandboxes or WebAssembly
   * Use modern language features to prevent buffer overflows and race conditions

10. **Implement Robust Data-Driven Architecture**
    * Keep the core engine agnostic to content; treat logic and rules as data
    * Enable hot-reloading of assets and scripts without full engine restarts

---

# Game Engine Code (code.engine.game)

1. **Separate Logic and Data**
   * Use Component-Based or Entity Component System (ECS) architecture instead of monolithic classes
   * Make game objects flexible collections of data and behavior

2. **Avoid Hardcoding Values and Magic Numbers**
   * Define all tunable parameters (speed, gravity, damage) in configuration files or named constants
   * Never embed raw numbers directly into logic

3. **Implement Object Pooling**
   * Avoid frequent instantiation and destruction that causes garbage collection spikes
   * Reuse objects from a pre-allocated pool to maintain consistent frame rates

4. **Keep the Update Loop Lean**
   * Minimize heavy calculations, string manipulations, or nested lookups in high-frequency ticks
   * Use event-driven designs, timers, or alarms for tasks that don't need per-frame execution

5. **Structure Your Project Hierarchically**
   * Maintain clean asset and source directories grouped by purpose
   * Organize scripts, scenes, shaders, prefabs, and audio into dedicated folders

6. **Manage Memory and Cache Locality**
   * Store related data sequentially in memory to maximize CPU cache hits
   * This is especially critical for performance-intensive systems like physics or particles

7. **Profile Before Optimizing**
   * Use built-in or external profilers to identify actual bottlenecks
   * Don't guess where CPU, GPU, or memory spikes occur

8. **Follow Single Responsibility Principle**
   * Ensure each class, node, or module handles only one specific part of the game
   * Separate concerns like input handling, physics, and rendering

9. **Use Version Control Correctly**
   * Track source code and text-based assets with Git
   * Use Git LFS for large binary assets and maintain proper .gitignore rules

10. **Write Intentional, Clean Comments**
    * Focus on why a complex architectural workaround exists
    * Don't comment on syntax if the code is already readable and self-explanatory

---

# FPS Game Engine Code

1. **Separate Input Handling from Frame Rate**
   * Gather and process raw mouse and keyboard input on a dedicated high-frequency thread
   * Avoid delta-time scaling for mouse look to prevent input judder during aim

2. **Implement Sub-Tick Input and Physics**
   * Capture input timestamps at the exact moment they occur, not at the next tick
   * Send precise timestamps to the server so hit registration occurs at the exact sub-tick moment

3. **Use Client-Side Prediction and Server Reconciliation**
   * Simulate the local player's movement immediately without waiting for server response
   * Maintain a rolling buffer of inputs and states; re-simulate when server sends authoritative data

4. **Build Lag Compensation via Backward Reconciliation**
   * Rewind time: check hits against historical enemy positions, not current positions
   * Maintain a history buffer up to 200–300 milliseconds to resolve "I shot him on my screen" issues

5. **Utilize Ray-Cast and Hitbox Pooling**
   * Pre-allocate bullet trajectories, impact particles, and bounding volumes
   * Avoid dynamic instantiation to prevent garbage collection spikes

6. **Implement Dynamic Entity Component Systems for Data Locality**
   * Process hundreds of entities with cache-optimized memory layouts
   * Structure data as Arrays of Structures converted to Structures of Arrays for SIMD vectorization

7. **Optimize Spatial Partitioning for Ray-Casts**
   * Use Bounding Volume Hierarchies, Octrees, or Loose Voxels for fast line-segment intersections
   * Update dynamic entities efficiently using loose boundaries to minimize rebuilding costs

8. **Prioritize Network Delta Compression and Interest Management**
   * Transmit only variables that changed and pack integers/floats to minimum necessary bits
   * Implement Interest Management to replicate data only to clients within relevant zones

9. **Optimize Audio Propagation and Spatialization**
   * Treat sound propagation similarly to AI pathfinding for realistic occlusion
   * Use low-resolution geometry grids to calculate acoustic diffraction in real-time

10. **Establish Strict Determinism in Physics**
    * Run core gameplay and physics simulation on a fixed time step independent of frame rate
    * Ensure floating-point math behaves identically across architectures to prevent desynchronization
