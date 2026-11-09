import { describe, expect, it } from "vitest";
import { cubicBezier, ease } from "./camera";

describe("camera easing", () => {
  it("is the identity for the linear curve", () => {
    const linear = cubicBezier(0, 0, 1, 1);
    for (const x of [0, 0.1, 0.33, 0.5, 0.9, 1]) expect(linear(x)).toBeCloseTo(x, 4);
  });

  it("agrees with dense sampling of the curve's parametric form", () => {
    // An independent oracle: sample (x(t), y(t)) finely and read y where x crosses each point.
    const [x1, y1, x2, y2] = [0.25, 0.8, 0.3, 1];
    const bez = (a: number, b: number, t: number) => 3 * a * t * (1 - t) ** 2 + 3 * b * t * t * (1 - t) + t ** 3;
    const solve = cubicBezier(x1, y1, x2, y2);
    for (const x of [0.05, 0.2, 0.5, 0.8, 0.95]) {
      let t = 0;
      while (bez(x1, x2, t) < x) t += 1e-5;
      expect(solve(x)).toBeCloseTo(bez(y1, y2, t), 3);
    }
  });

  it("runs the shared curve from 0 to 1 without going back", () => {
    let last = 0;
    for (let i = 0; i <= 100; i++) {
      const v = ease(i / 100);
      expect(v).toBeGreaterThanOrEqual(last - 1e-9);
      last = v;
    }
    expect(ease(0)).toBe(0);
    expect(ease(1)).toBe(1);
    // A fast start: more than half the way at a quarter of the time.
    expect(ease(0.25)).toBeGreaterThan(0.5);
  });
});
