import { describe, expect, it } from "vitest";
import type { AnnotationDto } from "../api/dto";
import { suggestThreshold } from "../domain/thresholds";
import type { Judgment } from "../domain/types";
import { seedRecords } from "./generator";
import { seedDemoAnnotations } from "./demoAnnotations";

describe("seedDemoAnnotations", () => {
  const records = seedRecords(240, Date.parse("2026-11-22T00:00:00Z"));
  const by = new Map<string, AnnotationDto[]>();
  const anns = seedDemoAnnotations(records, by);

  it("jest deterministyczne i ocenia większość rekordów kilkoma analitykami", () => {
    expect(seedDemoAnnotations(records, new Map()).length).toBe(anns.length);
    expect(new Set(anns.map((a) => a.annotator)).size).toBe(3);
    expect(by.size).toBeGreaterThan(records.length / 2);
  });

  it("czynniki rekordu zgadzają się z tym, co backend uzna za komplet (M2: wszystkie reguły rekordu)", () => {
    const m2 = records.find((r) => r.module === 2 && by.has(r.id))!;
    expect(Object.keys(by.get(m2.id)![0].answers).sort()).toEqual(m2.rule_results!.map((x) => x.rule_id).sort());
  });

  it("dane demo pokazują sens progów per reguła: dla reguły 4 sugestia wyższa niż dla 5", () => {
    const judgments = (factor: string): Judgment[] =>
      records.filter((r) => r.module === 2).flatMap((r) =>
        (by.get(r.id) ?? []).map((a) => ({ recordId: r.id, module: 2 as const, annotator: a.annotator, factor, human: a.answers[factor] ?? null, score: r.rule_results!.find((x) => x.rule_id === factor)?.score ?? null })),
      );
    const s4 = suggestThreshold(judgments("4"));
    const s5 = suggestThreshold(judgments("5"));
    expect(s4).not.toBeNull();
    expect(s5).not.toBeNull();
    expect(s4!).toBeGreaterThan(s5!);
  });
});
