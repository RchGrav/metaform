// A small raw dump written by hand for the tests: one Definitive element, two more project
// elements, one party the project serves, one dependency, a layer definition and a root record.

import type { RawDump } from "../../source/types";

/** The hand-written dump. Tests must not alter it. */
export const handDump: RawDump = {
  ".": {
    specification: [{ text: "A note at the root." }],
    code: {
      engine: {
        game: {
          technical_name: "game engine",
          name: "Quake core",
          role: "Definitive",
          uri: "./src/engine.c",
          sources: ["./docs/engine.md", { path: "./docs/loop.md" }, "./src/engine.c"],
          specification: [
            { text: "The engine draws and simulates." },
            { level: 1, title: "Frame loop", text: "One pass per frame." },
            { level: 2, code: "R-1.2", title: "Timing", text: "A frame takes 16 ms." },
          ],
          wants: {
            "upstream.code.engine.physics": { why: "resolve collisions", how: "steps rigid bodies", direction: "two-way" },
            "code.bus.data.event": { why: "receive player input", how: "dispatches event streams", direction: "inbound" },
          },
        },
      },
      bus: { data: { event: { technical_name: "event data bus", name: "Pulsar router", role: "Supportive" } } },
      queue: { dead_letter: { technical_name: "dead letter queue", status: "un_built" } },
    },
    data: { schema: { message: { name: "Wire | format", role: "Divergent", uri: "./src/wire.h" } } },
    downstream: {
      developer: {
        game: {
          technical_name: "game developer",
          name: "Studio developer",
          role: "Notable",
          wants: {
            "code.engine.game": { why: "build a playable game", how: "provides the frame loop", direction: "inbound" },
          },
        },
      },
    },
    upstream: {
      code: {
        engine: {
          physics: { technical_name: "physics engine", name: "Bullet", role: "Supportive", uri: "https://example.org/bullet" },
        },
      },
    },
    layer: {
      document: {
        specification: {
          technical_name: "specification document layer",
          name: "Specification",
          role: "Supportive",
          description: "Prose that the skeleton leaves out.",
          instruction: "Write each block in plain English.",
        },
      },
    },
  },
};
