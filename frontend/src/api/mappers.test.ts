import { describe, expect, it } from "vitest";
import type { RecordDto } from "./dto";
import { toRecord, toRecordDto } from "./mappers";

const dto: RecordDto = {
  id: "r1", module: 2, detected_at: "2026-11-01T00:00:00Z", source: "Mastodon", url: "https://a.pl", title: "T", content: "C",
  risk_score: 0.77, status: "in_review", entity: { name: "N", kind: "investment_firm", url: null },
  rule_results: [{ rule_id: "12a", verdict: "fail", score: 0.9, note: null }], evidence: null, ground_truth: null,
};

describe("toRecord", () => {
  it("mapuje snake_case na model domenowy i normalizuje null", () => {
    const r = toRecord(dto);
    expect(r.score).toBe(0.77);
    expect(r.detectedAt).toBe(dto.detected_at);
    expect(r.entity.url).toBeUndefined();
    expect(r.rules?.[0]).toEqual({ ruleId: "12a", verdict: "fail", score: 0.9, note: undefined });
    expect(r.evidence).toEqual([]);
    expect(r.groundTruth).toBeUndefined();
  });
  it("platforma z backendu (małe litery) trafia do etykiety źródła", () => {
    expect(toRecord({ ...dto, source: "youtube" }).source).toBe("YouTube");
    expect(toRecord({ ...dto, source: "telegram" }).source).toBe("Telegram");
  });
  it("mapuje obrazy z wariantami, obserwację, datę publikacji i flagę manipulated", () => {
    const r = toRecord({
      ...dto,
      published_at: "2026-10-30T00:00:00Z",
      observation_id: "3",
      manipulated: true,
      manipulated_rules: ["8"],
      images: [{ variant: "desktop", focus: "page", url: "/api/records/r1/images/desktop?focus=page" }],
    });
    expect(r).toMatchObject({ publishedAt: "2026-10-30T00:00:00Z", observationId: "3", manipulated: true, manipulatedRules: ["8"] });
    expect(r.images).toEqual([{ variant: "desktop", focus: "page", url: "/api/records/r1/images/desktop?focus=page" }]);
    expect(toRecord(dto)).toMatchObject({ images: [], manipulated: false, observationId: undefined });
  });
  it("nieznane źródło trafia do WWW", () => expect(toRecord(dto).source).toBe("WWW"));
  it("round-trip zachowuje kluczowe pola", () => expect(toRecord(toRecordDto(toRecord(dto)))).toEqual(toRecord(dto)));
});
