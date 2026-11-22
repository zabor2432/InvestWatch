import { describe, expect, it } from "vitest";
import { parseFilters, serializeFilters } from "./useFilters";

describe("filtry w URL", () => {
  it("round-trip", () => {
    const f = { q: "kuba", modules: [1, 3] as (1 | 2 | 3)[], sources: ["TikTok" as const], levels: ["high" as const], statuses: [], from: "2026-11-01", to: "" };
    expect(parseFilters(serializeFilters(f))).toEqual(f);
  });
  it("ignoruje nieznane wartości i zachowuje obce parametry", () => {
    expect(parseFilters("?m=1,9&r=zly").modules).toEqual([1]);
    expect(serializeFilters(parseFilters(""), "?x=1")).toBe("?x=1");
  });
});
