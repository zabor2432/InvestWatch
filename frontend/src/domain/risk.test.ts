import { describe, expect, it } from "vitest";
import { applyFilters, EMPTY_FILTERS } from "./filters";
import { clampThreshold, confusionAt, riskLevel } from "./risk";
import type { IncidentRecord } from "./types";

const rec = (id: string, score: number, groundTruth?: boolean, extra: Partial<IncidentRecord> = {}): IncidentRecord => ({
  id, module: 1, detectedAt: "2026-11-10T10:00:00Z", source: "WWW", url: "https://x.pl", title: "t", content: "c", score,
  status: "new", entity: { name: "Firma", kind: "unauthorized" }, evidence: [], images: [], manipulated: false, groundTruth, ...extra,
});

describe("confusionAt", () => {
  const data = [rec("a", 0.9, true), rec("b", 0.7, false), rec("c", 0.4, true), rec("d", 0.2, false), rec("e", 0.95)];
  it("liczy TP/FP/FN/TN i pomija rekordy bez etykiety", () => {
    const c = confusionAt(data, 0.6);
    expect([c.tp, c.fp, c.fn, c.tn]).toEqual([1, 1, 1, 1]);
    expect(c.precision).toBe(0.5);
    expect(c.recall).toBe(0.5);
    expect(c.flagged).toBe(3);
  });
  it("wyższy próg obniża FP i podnosi FN", () => {
    const lo = confusionAt(data, 0.3), hi = confusionAt(data, 0.8);
    expect(hi.fp).toBeLessThan(lo.fp);
    expect(hi.fn).toBeGreaterThan(lo.fn);
  });
  it("zwraca null gdy dzielnik wynosi 0", () => {
    expect(confusionAt(data, 1).precision).toBeNull();
  });
});

describe("clampThreshold / riskLevel", () => {
  it("przycina do 0..1 i obsługuje NaN", () => {
    expect(clampThreshold(1.7)).toBe(1);
    expect(clampThreshold(-2)).toBe(0);
    expect(clampThreshold(NaN)).toBe(0.5);
  });
  it("mapuje pasma ryzyka", () => {
    expect([riskLevel(0.2), riskLevel(0.5), riskLevel(0.8)]).toEqual(["low", "medium", "high"]);
  });
});

describe("applyFilters", () => {
  const data = [rec("a", 0.9, undefined, { module: 2, source: "TikTok" }), rec("b", 0.7, undefined, { module: 3 }), rec("c", 0.3)];
  it("odrzuca rekordy poniżej progu", () => expect(applyFilters(data, EMPTY_FILTERS, 0.5).map((r) => r.id)).toEqual(["a", "b"]));
  it("filtruje po module i źródle", () => {
    expect(applyFilters(data, { ...EMPTY_FILTERS, modules: [2] }, 0).map((r) => r.id)).toEqual(["a"]);
    expect(applyFilters(data, { ...EMPTY_FILTERS, sources: ["TikTok"] }, 0).map((r) => r.id)).toEqual(["a"]);
  });
  it("filtruje po zakresie dat", () => {
    expect(applyFilters(data, { ...EMPTY_FILTERS, from: "2026-11-11" }, 0)).toHaveLength(0);
    expect(applyFilters(data, { ...EMPTY_FILTERS, from: "2026-11-10", to: "2026-11-10" }, 0)).toHaveLength(3);
  });
});
