import { describe, expect, it } from "vitest";
import { chooseSource } from "./choose";

describe("chooseSource", () => {
  it("uses the host when the host's mark is in the page", () => {
    expect(chooseSource("", true)).toBe("host");
    expect(chooseSource("?first-run", true)).toBe("host");
  });
  it("uses the simulated data when no host serves the page", () => {
    expect(chooseSource("", false)).toBe("mock");
  });
  it("lets ?mock win over the host's mark", () => {
    expect(chooseSource("?mock", true)).toBe("mock");
    expect(chooseSource("?x=1&mock=", true)).toBe("mock");
  });
});
