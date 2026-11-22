import { RULES_BY_ID } from "./rules";
import { globalOf, thresholdFor, type ThresholdInput } from "./thresholds";
import type { Answer, IncidentRecord } from "./types";

/** Odpowiedź modelu na czynnik wg progu (null = nie dotyczy). */
export interface ModelAnswer {
  answer: Answer;
  score: number | null;
}

export interface Factor {
  id: string;
  name: string;
  sub?: string;
  okLabel: string;
  flagLabel: string;
  model: ModelAnswer;
}

/** Czynniki do ręcznej oceny: moduł 1 i 3 po jednym, moduł 2 wszystkie reguły rekordu. */
export function factorsOf(r: IncidentRecord, threshold: ThresholdInput): Factor[] {
  const flagged = (r.score >= globalOf(threshold) ? 1 : 0) as Answer;
  if (r.module === 1) {
    return [{ id: "is_ad", name: "Materiał jest reklamą produktów lub usług finansowych", okLabel: "Nie reklama", flagLabel: "Reklama", model: { answer: flagged, score: r.score } }];
  }
  if (r.module === 3) {
    return [{ id: "offers_advisory", name: "Podmiot oferuje doradztwo inwestycyjne bez uprawnień", okLabel: "Brak doradztwa", flagLabel: "Doradztwo", model: { answer: flagged, score: r.score } }];
  }
  return (r.rules ?? []).map((x) => ({
    id: x.ruleId,
    name: RULES_BY_ID[x.ruleId]?.name ?? `Reguła ${x.ruleId}`,
    sub: RULES_BY_ID[x.ruleId]?.legalBasis,
    okLabel: "Spełnia",
    flagLabel: "Narusza",
    model: x.verdict === "n/a" ? { answer: null, score: null } : { answer: x.score >= thresholdFor(threshold, 2, x.ruleId) ? 1 : 0, score: x.score },
  }));
}

/** Zgodność odpowiedzi oceniającego z modelem na czynnikach, które model rozstrzygnął. */
export function agreement(factors: Factor[], answers: Record<string, Answer | undefined>) {
  let agree = 0, comparable = 0;
  for (const f of factors) {
    const mine = answers[f.id];
    if (mine === undefined) continue;
    comparable++;
    if (mine === f.model.answer) agree++;
  }
  return { agree, comparable };
}

const FACTOR_NAMES: Record<string, string> = { is_ad: "Czy to reklama", offers_advisory: "Doradztwo bez uprawnień" };

/** Krótka nazwa czynnika (reguły: nazwa z załącznika UKNF). */
export const factorName = (id: string) => RULES_BY_ID[id]?.name ?? FACTOR_NAMES[id] ?? id;
