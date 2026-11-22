import { describe, expect, it } from "vitest";
import { deviations, filterJudgments, histogram, interAnnotator, perAnnotator, perFactor, stats } from "./report";
import type { Answer, Judgment } from "./types";

const j = (recordId: string, human: Answer, score: number | null, annotator = "Ola", factor = "5", module: 1 | 2 | 3 = 2): Judgment => ({ recordId, module, annotator, factor, human, score });

describe("stats", () => {
  const data = [j("1", 1, 0.9), j("2", 1, 0.2), j("3", 0, 0.8), j("4", 0, 0.1), j("5", 0, 0.1), j("6", null, 0.9), j("7", 1, null)];
  it("liczy macierz pomyłek tylko na ocenach porównywalnych (bez 'nie dotyczy')", () => {
    const s = stats(data, 0.5);
    expect([s.tp, s.fp, s.fn, s.tn, s.n]).toEqual([1, 1, 1, 2, 5]);
    expect(s.agreement).toBeCloseTo(3 / 5);
    expect(s.precision).toBeCloseTo(0.5);
    expect(s.recall).toBeCloseTo(0.5);
    expect(s.f1).toBeCloseTo(0.5);
    expect(s.kappa).toBeCloseTo(0.1666, 3); // po=0.6, pe=0.52
  });
  it("próg zmienia werdykt modelu", () => {
    expect(stats(data, 0.15).tp).toBe(2); // 0.2 i 0.9 >= 0.15
    expect(stats([], 0.5)).toMatchObject({ n: 0, agreement: null, kappa: null });
  });
});

describe("perFactor", () => {
  it("średnie score wg oceny człowieka i maksimum na zgodnych (baseline progu)", () => {
    const rows = perFactor([j("1", 1, 0.9), j("2", 1, 0.7), j("3", 0, 0.3), j("4", 0, 0.5), j("5", null, 0.2), j("6", 1, 0.8, "Ola", "2")], 0.6);
    const r5 = rows.find((r) => r.factor === "5")!;
    expect(r5).toMatchObject({ judgments: 5, n: 4, meanFlagged: 0.8, maxOk: 0.5 });
    expect(r5.meanOk).toBeCloseTo(0.4);
    expect(rows.map((r) => r.factor)).toEqual(["2", "5"]); // sortowanie naturalne
  });
});

describe("deviations", () => {
  it("rozbieżności od najbardziej pewnych błędów modelu", () => {
    const d = deviations([j("1", 0, 0.95), j("2", 1, 0.4), j("3", 1, 0.9), j("4", 0, 0.7)], 0.6);
    expect(d.map((x) => x.recordId)).toEqual(["1", "4", "2"]); // dystanse: 0.95, 0.70, 0.60
    expect(deviations([j("1", 0, 0.95), j("2", 0, 0.9)], 0.6, 1)).toHaveLength(1);
  });
});

describe("interAnnotator", () => {
  it("zgodność liczona tylko dla czynników ocenionych przez >= 2 osoby", () => {
    const r = interAnnotator([j("1", 1, 0.9, "Ola"), j("1", 1, 0.9, "Jan"), j("2", 0, 0.1, "Ola"), j("2", 1, 0.1, "Jan"), j("3", 1, 0.5, "Ola")]);
    expect(r.shared).toBe(2);
    expect(r.agreement).toBe(0.5);
    expect(r.conflicts).toEqual([{ recordId: "2", module: 2, factor: "5", answers: { Ola: 0, Jan: 1 } }]);
  });
});

describe("filtry, oceniający i histogram", () => {
  it("filtruje po module i oceniających", () => {
    const js = [j("1", 1, 0.9, "Ola", "5", 2), j("2", 1, 0.9, "Jan", "is_ad", 1)];
    expect(filterJudgments(js, { module: 2, annotators: [] })).toHaveLength(1);
    expect(filterJudgments(js, { module: "all", annotators: ["Jan"] })[0].recordId).toBe("2");
    expect(perAnnotator(js, 0.5).map((a) => [a.annotator, a.agreement])).toEqual([["Jan", 1], ["Ola", 1]]);
  });
  it("histogram dzieli score na przedziały wg oceny człowieka", () => {
    const h = histogram([j("1", 1, 0.95), j("2", 0, 0.05), j("3", 0, 1.0), j("4", 1, null)]);
    expect(h).toHaveLength(10);
    expect([h[0].ok, h[9].flagged, h[9].ok]).toEqual([1, 1, 1]); // score 1.0 trafia do ostatniego przedziału
  });
});
