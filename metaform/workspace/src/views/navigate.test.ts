import { describe, expect, it } from "vitest";
import { nearestInDirection } from "./navigate";

describe("arrow keys along wants", () => {
  const centres = new Map([
    ["code", { x: 500, y: 400 }],
    ["upstream", { x: 200, y: 250 }],
    ["document", { x: 520, y: 250 }],
    ["downstream", { x: 850, y: 260 }],
    ["far-right", { x: 1400, y: 400 }],
  ]);
  const near = ["upstream", "document", "downstream"];

  it("picks the connected element most nearly in each direction", () => {
    expect(nearestInDirection("code", near, centres, "ArrowUp")).toBe("document");
    expect(nearestInDirection("code", near, centres, "ArrowLeft")).toBe("upstream");
    expect(nearestInDirection("code", near, centres, "ArrowRight")).toBe("downstream");
  });

  it("does nothing when no connected element lies that way", () => {
    expect(nearestInDirection("code", near, centres, "ArrowDown")).toBeNull();
    expect(nearestInDirection("code", [], centres, "ArrowUp")).toBeNull();
  });

  it("prefers a nearer element ahead to a farther one slightly off the line", () => {
    expect(nearestInDirection("code", ["downstream", "far-right"], centres, "ArrowRight")).toBe("downstream");
  });
});
