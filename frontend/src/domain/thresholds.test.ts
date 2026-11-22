import { describe, expect, it } from "vitest";
import { confusionAt } from "./risk";
import { applyFilters, EMPTY_FILTERS } from "./filters";
import { isFlagged, suggestThreshold, thresholdFor } from "./thresholds";
import { perFactor } from "./report";
import type { IncidentRecord, Judgment } from "./types";

const j = (human: 0 | 1 | null, score: number | null, factor = "4", recordId = "r"): Judgment => ({ recordId, module: 2, annotator: "Ola", factor, human, score });
const m2 = (id: string, rules: Record<string, number>, groundTruth?: boolean): IncidentRecord => ({
  id, module: 2, detectedAt: "2026-11-10T10:00:00Z", source: "WWW", url: "u", title: "t", content: "c",
  score: Math.max(...Object.values(rules)), status: "new", entity: { name: "F", kind: "investment_firm" },
  rules: Object.entries(rules).map(([ruleId, score]) => ({ ruleId, verdict: "pass" as const, score })),
  evidence: [], images: [], manipulated: false, groundTruth,
});

describe("thresholdFor / isFlagged", () => {
  it("reguła bez nadpisania używa progu globalnego, moduły 1 i 3 zawsze globalnego", () => {
    const t = { global: 0.5, rules: { "4": 0.8 } };
    expect([thresholdFor(t, 2, "4"), thresholdFor(t, 2, "5"), thresholdFor(t, 1, "4"), thresholdFor(0.3, 2, "4")]).toEqual([0.8, 0.5, 0.5, 0.3]);
  });
  it("rekord M2 jest flagowany, gdy którakolwiek reguła przekracza własny próg", () => {
    const r = m2("a", { "4": 0.65, "5": 0.2 });
    expect(isFlagged(r, { global: 0.5, rules: {} })).toBe(true);
    expect(isFlagged(r, { global: 0.5, rules: { "4": 0.7 } })).toBe(false); // próg reguły 4 podniesiony
  });
  it("filtr listy, macierz pomyłek i statystyki korzystają z progów per reguła", () => {
    const records = [m2("a", { "4": 0.65 }, false), m2("b", { "4": 0.9 }, true)];
    const t = { global: 0.5, rules: { "4": 0.7 } };
    expect(applyFilters(records, EMPTY_FILTERS, t).map((r) => r.id)).toEqual(["b"]);
    expect(confusionAt(records, t)).toMatchObject({ tp: 1, fp: 0 });
    expect(confusionAt(records, 0.5)).toMatchObject({ tp: 1, fp: 1 });
    const js = [j(0, 0.65), j(1, 0.9)];
    expect(perFactor(js, t)[0]).toMatchObject({ tp: 1, fp: 0, agreement: 1 });
  });
});

describe("suggestThreshold", () => {
  it("podnosi próg, gdy większość zgodnych ma wysoki score (przypadek 'rozmiar tekstu')", () => {
    const js = [...[0.55, 0.6, 0.62, 0.65, 0.68, 0.66].map((s) => j(0, s)), j(1, 0.9), j(1, 0.85)];
    const s = suggestThreshold(js)!;
    expect(s).toBeGreaterThan(0.68);
    expect(s).toBeLessThanOrEqual(0.85); // wszystkie naruszenia nadal wykryte
  });
  it("przy dobrze rozdzielonych ocenach wybiera próg pomiędzy grupami", () => {
    const js = [...[0.1, 0.2, 0.3].map((s) => j(0, s)), ...[0.7, 0.8, 0.9].map((s) => j(1, s))];
    const s = suggestThreshold(js)!;
    expect(s).toBeGreaterThan(0.3);
    expect(s).toBeLessThanOrEqual(0.7);
  });
  it("bez naruszeń wg analityków: tuż nad najwyższym score zgodnych; bez próbki: null", () => {
    expect(suggestThreshold([0.2, 0.4, 0.55, 0.3, 0.1].map((s) => j(0, s)))).toBe(0.6);
    expect(suggestThreshold([j(0, 0.2), j(1, 0.9)])).toBeNull();
    expect(suggestThreshold([j(null, 0.9), j(0, null), j(0, 0.1), j(0, 0.2), j(0, 0.3)])).toBeNull(); // 'nie dotyczy' się nie liczy
  });
});
