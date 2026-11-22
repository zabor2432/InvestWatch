import { describe, expect, it } from "vitest";
import { fmtAgo, fmtDateTime, fmtPct, fmtScore, isImagePreview } from "./format";

describe("format helpers", () => {
  it("formats probabilities as percentages and scores with two decimal places", () => {
    expect(fmtPct(0.75)).toBe("75%");
    expect(fmtPct(null)).toBe("—");
    expect(fmtScore(0.756)).toBe("0,76");
    expect(fmtScore(Number.NaN)).toBe("—");
  });

  it("formats valid dates and handles invalid date strings", () => {
    expect(fmtDateTime("not a date")).toBe("—");
    expect(fmtDateTime("2026-01-02T03:04:00Z")).not.toBe("—");
    expect(fmtAgo("not a date")).toBe("—");
    expect(fmtAgo(new Date(Date.now() - 5 * 60_000).toISOString())).toContain("5");
  });

  it("recognizes screenshot and snapshot evidence as image previews", () => {
    expect(isImagePreview({ kind: "screenshot", label: "Screenshot", value: "image.png" })).toBe(true);
    expect(isImagePreview({ kind: "snapshot", label: "Snapshot", value: "image.png" })).toBe(true);
    expect(isImagePreview({ kind: "phrase", label: "Phrase", value: "example" })).toBe(false);
  });
});
