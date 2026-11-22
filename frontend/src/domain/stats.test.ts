import { describe, expect, it } from "vitest";
import { computeKpis, dailyTrend, perModule, riskDistribution } from "./stats";
import type { IncidentRecord } from "./types";

const NOW = new Date("2026-11-21T12:00:00").getTime();
const rec = (id: string, hoursAgo: number, score = 0.9, module: 1 | 2 | 3 = 1, status: IncidentRecord["status"] = "new"): IncidentRecord => ({
  id, module, detectedAt: new Date(NOW - hoursAgo * 3600000).toISOString(), source: "WWW", url: "u", title: "t", content: "c", score, status,
  entity: { name: "n", kind: "unauthorized" }, evidence: [], images: [], manipulated: false,
});

describe("dailyTrend", () => {
  it("zwraca zera dla pustych dni i grupuje po module", () => {
    const t = dailyTrend([rec("a", 1), rec("b", 2, 0.9, 2), rec("c", 30, 0.9, 3)], 3, NOW);
    expect(t).toHaveLength(3);
    expect(t.map((d) => d.total)).toEqual([0, 1, 2]);
    expect(t[2][1]).toBe(1);
    expect(t[2][2]).toBe(1);
    expect(t[1][3]).toBe(1);
  });
  it("pomija rekordy spoza okna", () => expect(dailyTrend([rec("old", 24 * 40)], 7, NOW).every((d) => d.total === 0)).toBe(true));
});

describe("computeKpis", () => {
  it("liczy okna 24h, wysokie ryzyko i confirmRate", () => {
    const k = computeKpis([rec("a", 1), rec("b", 30, 0.3, 1, "confirmed"), rec("c", 40, 0.6, 2, "false_positive"), rec("d", 5, 0.85, 3, "in_review")], NOW);
    expect(k.last24h).toBe(2);
    expect(k.prev24h).toBe(2);
    expect(k.high).toBe(2);
    expect(k.toReview).toBe(2);
    expect(k.confirmRate).toBe(0.5);
  });
  it("confirmRate = null bez rozstrzygnięć", () => expect(computeKpis([rec("a", 1)], NOW).confirmRate).toBeNull());
});

describe("rozkłady", () => {
  it("riskDistribution i perModule", () => {
    const d = [rec("a", 1, 0.9), rec("b", 1, 0.6, 2), rec("c", 1, 0.1, 2)];
    expect(riskDistribution(d)).toEqual({ high: 1, medium: 1, low: 1 });
    expect(perModule(d)).toEqual({ 1: 1, 2: 2, 3: 0 });
  });
});
