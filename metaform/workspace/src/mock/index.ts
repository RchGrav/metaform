import data from "./workspace.json";
import { MockSource, type MockOptions } from "./source";
import type { MockWorkspace } from "./workspace";

export { MockSource } from "./source";
export type { MockOptions } from "./source";
export type * from "./workspace";

/** The simulated workspace: three projects built from the repository's own maps. */
export const workspace = data as unknown as MockWorkspace;

export function createMockSource(options?: MockOptions): MockSource {
  return new MockSource(workspace, options);
}
