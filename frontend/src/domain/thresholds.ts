import type { IncidentRecord, Judgment, ModuleId } from "./types";

/** Próg globalny plus nadpisania per reguła modułu 2 (reguła bez nadpisania używa globalnego). */
export interface Thresholds {
  global: number;
  rules: Record<string, number>;
}

/** Funkcje domeny przyjmują zwykłą liczbę (jeden próg dla wszystkiego) albo `Thresholds`. */
export type ThresholdInput = number | Thresholds;

export const thresholdFor = (t: ThresholdInput, module: ModuleId, factor: string): number =>
  typeof t === "number" ? t : module === 2 ? (t.rules[factor] ?? t.global) : t.global;

export const globalOf = (t: ThresholdInput): number => (typeof t === "number" ? t : t.global);

/** Rekord jest flagowany, gdy score ≥ próg; w module 2 gdy którakolwiek reguła przekracza własny próg. */
export function isFlagged(r: IncidentRecord, t: ThresholdInput): boolean {
  if (r.module === 2 && r.rules?.length) return r.rules.some((x) => x.verdict !== "n/a" && x.score >= thresholdFor(t, 2, x.ruleId));
  return r.score >= globalOf(t);
}

const MIN_FOR_SUGGESTION = 5;
const STEP = 0.05;

const f1At = (pairs: { human: 0 | 1; score: number }[], thr: number) => {
  let tp = 0, fp = 0, fn = 0;
  for (const p of pairs) {
    const flagged = p.score >= thr;
    if (flagged && p.human === 1) tp++;
    else if (flagged) fp++;
    else if (p.human === 1) fn++;
  }
  return tp === 0 ? 0 : (2 * tp) / (2 * tp + fp + fn);
};

/**
 * Sugerowany próg czynnika z ocen ręcznych: maksimum F1 na siatce co 0,05 (przy remisie środek przedziału remisu);
 * gdy analitycy nigdzie nie widzą naruszenia, tuż powyżej najwyższego score uznanego za zgodny. null = za mało ocen.
 */
export function suggestThreshold(js: Judgment[]): number | null {
  const pairs = js.filter((j): j is Judgment & { human: 0 | 1; score: number } => j.human !== null && j.score !== null);
  if (pairs.length < MIN_FOR_SUGGESTION) return null;
  const clamp = (v: number) => Math.min(1, Math.round(v * 100) / 100);
  if (!pairs.some((p) => p.human === 1)) return clamp(Math.ceil((Math.max(...pairs.map((p) => p.score)) + 1e-9) / STEP) * STEP);
  const grid = Array.from({ length: Math.round(1 / STEP) + 1 }, (_, i) => clamp(i * STEP));
  const scored = grid.map((t) => ({ t, f1: f1At(pairs, t) }));
  const best = Math.max(...scored.map((s) => s.f1));
  const ties = scored.filter((s) => Math.abs(s.f1 - best) < 1e-9).map((s) => s.t);
  return ties[Math.floor((ties.length - 1) / 2)];
}
