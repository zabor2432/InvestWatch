import { describe, expect, it } from "vitest";
import { agreement, factorsOf } from "./factors";
import type { IncidentRecord, RuleVerdict } from "./types";

const base: IncidentRecord = { id: "1", module: 1, detectedAt: "", source: "WWW", url: "u", title: "t", content: "c", score: 0.9, status: "new", entity: { name: "n", kind: "finfluencer" }, evidence: [], images: [], manipulated: false };
const rule = (ruleId: string, verdict: RuleVerdict, score = 0.5) => ({ ruleId, verdict, score });

describe("factorsOf", () => {
  it("moduł 1 i 3: jeden czynnik, odpowiedź modelu wg progu", () => {
    const m1 = factorsOf(base, 0.6);
    expect(m1.map((f) => f.id)).toEqual(["is_ad"]);
    expect(m1[0].model).toEqual({ answer: 1, score: 0.9 });
    expect(factorsOf({ ...base, module: 3, score: 0.3 }, 0.6)[0]).toMatchObject({ id: "offers_advisory", model: { answer: 0 } });
  });

  it("moduł 2: wszystkie reguły rekordu, odpowiedź wg progu (n/a osobno)", () => {
    const rec = { ...base, module: 2 as const, rules: [rule("2", "fail", 0.9), rule("3", "pass", 0.1), rule("8", "n/a", 0), rule("9", "uncertain", 0.55)] };
    const f = factorsOf(rec, 0.6);
    expect(f.map((x) => x.id)).toEqual(["2", "3", "8", "9"]);
    expect(f.map((x) => x.model.answer)).toEqual([1, 0, null, 0]); // 0.55 < próg 0.6
    expect(f[2].model.score).toBeNull();
    expect(f[0]).toMatchObject({ name: "Oznaczenie reklamy", okLabel: "Spełnia", flagLabel: "Narusza" });
  });
});

describe("agreement", () => {
  it("liczy zgodność tylko tam, gdzie model rozstrzygnął, a użytkownik odpowiedział", () => {
    const rec = { ...base, module: 2 as const, rules: [rule("2", "fail", 0.9), rule("3", "pass", 0.1), rule("8", "n/a"), rule("9", "uncertain", 0.55)] };
    const f = factorsOf(rec, 0.6);
    expect(agreement(f, { "2": 1, "3": 1, "8": null, "9": 0 })).toEqual({ agree: 3, comparable: 4 });
    expect(agreement(f, { "2": 1 })).toEqual({ agree: 1, comparable: 1 });
  });

  it("próg per reguła zmienia odpowiedź modelu tylko tej reguły", () => {
    const rec = { ...base, module: 2 as const, rules: [rule("4", "fail", 0.65), rule("5", "fail", 0.65)] };
    const f = factorsOf(rec, { global: 0.5, rules: { "4": 0.7 } });
    expect(f.map((x) => x.model.answer)).toEqual([0, 1]);
  });
});
