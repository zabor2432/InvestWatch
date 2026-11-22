import type { AnnotationDto, RecordDto } from "../api/dto";
import { rng } from "./generator";

const ANNOTATORS = ["Anna K.", "Piotr N.", "Marta W."];

/**
 * Prawdziwy próg analityków per reguła (w demo): wynik modelu poniżej niego analitycy uznają za zgodny.
 * Reguła 4 (rozmiar tekstu) jest "nadgorliwa" (model flaguje za dużo, trzeba podnieść próg), reguła 13 przeciwnie.
 */
const ANALYST_BAR: Record<string, number> = { "4": 0.82, "5": 0.5, "6": 0.68, "13": 0.38, "7": 0.75 };
const DEFAULT_BAR = 0.55;
const FLIP = 0.06; // analitycy też się mylą

/** Oceny ręczne wygenerowane pod demo (deterministyczne): moduł 2 per reguła, moduły 1 i 3 wg etykiety rekordu. */
export function seedDemoAnnotations(records: RecordDto[], byRecord: Map<string, AnnotationDto[]>): AnnotationDto[] {
  const r = rng(20261122);
  const out: AnnotationDto[] = [];
  for (const rec of records) {
    if (r() > (rec.module === 2 ? 0.85 : 0.5)) continue; // nie wszystko jest ocenione
    const raters = ANNOTATORS.filter(() => r() < 0.45);
    for (const annotator of raters.length ? raters : [ANNOTATORS[Math.floor(r() * ANNOTATORS.length)]]) {
      const flip = () => r() < FLIP;
      const bit = (truth: boolean): 0 | 1 => (truth !== flip() ? 1 : 0);
      const answers: AnnotationDto["answers"] =
        rec.module === 1 ? { is_ad: bit(!!rec.ground_truth) }
        : rec.module === 3 ? { offers_advisory: bit(!!rec.ground_truth) }
        : Object.fromEntries((rec.rule_results ?? []).map((x) => [x.rule_id, x.verdict === "n/a" ? null : bit(x.score >= (ANALYST_BAR[x.rule_id] ?? DEFAULT_BAR))]));
      const a: AnnotationDto = { id: out.length + 1, annotator, answers, created_at: new Date(Date.parse(rec.detected_at) + 3_600_000).toISOString() };
      out.push(a);
      byRecord.set(rec.id, [a, ...(byRecord.get(rec.id) ?? [])]);
    }
  }
  return out;
}
