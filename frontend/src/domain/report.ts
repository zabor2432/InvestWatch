import { thresholdFor, type ThresholdInput } from "./thresholds";
import type { Answer, Judgment, ModuleId } from "./types";

/** Porównywalne: człowiek rozstrzygnął (0/1) i model też (score); "nie dotyczy" po którejś stronie nie liczy się do metryk. */
const comparable = (j: Judgment): j is Judgment & { human: 0 | 1; score: number } => j.human !== null && j.score !== null;
const decision = (j: { module: ModuleId; factor: string; score: number }, t: ThresholdInput): 0 | 1 => (j.score >= thresholdFor(t, j.module, j.factor) ? 1 : 0);
const mean = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null);

export interface Filter {
  module: ModuleId | "all";
  annotators: string[]; // pusta = wszyscy
}

export const filterJudgments = (js: Judgment[], f: Filter) =>
  js.filter((j) => (f.module === "all" || j.module === f.module) && (f.annotators.length === 0 || f.annotators.includes(j.annotator)));

export interface Stats {
  n: number; // liczba porównywalnych ocen
  tp: number; fp: number; fn: number; tn: number; // 1 = oflagowane; człowiek = prawda
  agreement: number | null;
  precision: number | null;
  recall: number | null;
  f1: number | null;
  kappa: number | null; // zgodność poprawiona o przypadkową (Cohen)
}

const ratio = (a: number, b: number) => (b > 0 ? a / b : null);

export function stats(js: Judgment[], threshold: ThresholdInput): Stats {
  let tp = 0, fp = 0, fn = 0, tn = 0;
  for (const j of js) {
    if (!comparable(j)) continue;
    const m = decision(j, threshold);
    if (m === 1) j.human === 1 ? tp++ : fp++;
    else j.human === 1 ? fn++ : tn++;
  }
  const n = tp + fp + fn + tn;
  const precision = ratio(tp, tp + fp);
  const recall = ratio(tp, tp + fn);
  const f1 = precision !== null && recall !== null && precision + recall > 0 ? (2 * precision * recall) / (precision + recall) : null;
  const po = ratio(tp + tn, n);
  const pe = n ? ((tp + fp) * (tp + fn) + (fn + tn) * (fp + tn)) / (n * n) : null;
  const kappa = po !== null && pe !== null && pe < 1 ? (po - pe) / (1 - pe) : null;
  return { n, tp, fp, fn, tn, agreement: po, precision, recall, f1, kappa };
}

export interface FactorRow extends Stats {
  module: ModuleId;
  factor: string;
  judgments: number; // wszystkie oceny, także "nie dotyczy"
  meanFlagged: number | null; // średni score modelu tam, gdzie człowiek uznał naruszenie
  meanOk: number | null; // ... tam, gdzie zgodne
  maxOk: number | null; // najwyższy score na zgodnych: próg poniżej tej wartości daje fałszywe alarmy (baseline progu)
}

export function perFactor(js: Judgment[], threshold: ThresholdInput): FactorRow[] {
  const groups = new Map<string, Judgment[]>();
  for (const j of js) {
    const k = `${j.module}|${j.factor}`;
    groups.set(k, [...(groups.get(k) ?? []), j]);
  }
  return [...groups.entries()].map(([k, g]) => {
    const flagged = g.filter(comparable).filter((j) => j.human === 1).map((j) => j.score);
    const ok = g.filter(comparable).filter((j) => j.human === 0).map((j) => j.score);
    return { module: g[0].module, factor: g[0].factor, judgments: g.length, ...stats(g, threshold), meanFlagged: mean(flagged), meanOk: mean(ok), maxOk: ok.length ? Math.max(...ok) : null, _k: k } as FactorRow;
  }).sort((a, b) => a.module - b.module || a.factor.localeCompare(b.factor, "pl", { numeric: true }));
}

export interface AnnotatorRow { annotator: string; judgments: number; n: number; agreement: number | null }

export function perAnnotator(js: Judgment[], threshold: ThresholdInput): AnnotatorRow[] {
  const names = [...new Set(js.map((j) => j.annotator))].sort();
  return names.map((a) => {
    const g = js.filter((j) => j.annotator === a);
    const s = stats(g, threshold);
    return { annotator: a, judgments: g.length, n: s.n, agreement: s.agreement };
  });
}

export interface Deviation { recordId: string; module: ModuleId; factor: string; annotator: string; human: 0 | 1; score: number }

/** Rozbieżności model vs człowiek, od najbardziej "pewnych siebie" błędów modelu (największy dystans score od odpowiedzi człowieka). */
export function deviations(js: Judgment[], threshold: ThresholdInput, limit = 15): Deviation[] {
  return js.filter(comparable)
    .filter((j) => decision(j, threshold) !== j.human)
    .sort((a, b) => Math.abs(b.score - b.human) - Math.abs(a.score - a.human))
    .slice(0, limit)
    .map((j) => ({ recordId: j.recordId, module: j.module, factor: j.factor, annotator: j.annotator, human: j.human, score: j.score }));
}

export interface Conflict { recordId: string; module: ModuleId; factor: string; answers: Record<string, Answer> }

/** Zgodność między oceniającymi: czynniki ocenione przez co najmniej dwie osoby; konflikt = różne odpowiedzi. */
export function interAnnotator(js: Judgment[]) {
  const groups = new Map<string, Judgment[]>();
  for (const j of js) {
    const k = `${j.recordId}|${j.factor}`;
    groups.set(k, [...(groups.get(k) ?? []), j]);
  }
  const multi = [...groups.values()].filter((g) => g.length >= 2);
  const conflicts: Conflict[] = multi
    .filter((g) => new Set(g.map((j) => j.human)).size > 1)
    .map((g) => ({ recordId: g[0].recordId, module: g[0].module, factor: g[0].factor, answers: Object.fromEntries(g.map((j) => [j.annotator, j.human])) }));
  return { shared: multi.length, agreement: multi.length ? (multi.length - conflicts.length) / multi.length : null, conflicts };
}

export interface Bin { label: string; from: number; ok: number; flagged: number }

/** Rozkład score modelu dla czynnika, w podziale na ocenę człowieka (separacja = jak dobrze model rozróżnia). */
export function histogram(js: Judgment[], bins = 10): Bin[] {
  const out: Bin[] = Array.from({ length: bins }, (_, i) => ({ from: i / bins, label: (i / bins).toFixed(1), ok: 0, flagged: 0 }));
  for (const j of js.filter(comparable)) {
    const b = out[Math.min(bins - 1, Math.floor(j.score * bins))];
    if (j.human === 1) b.flagged++; else b.ok++;
  }
  return out;
}
