import { isFlagged, type ThresholdInput } from "./thresholds";
import type { IncidentRecord, RiskLevel } from "./types";

export const DEFAULT_THRESHOLD = 0.5;
const HIGH_RISK_FROM = 0.8;
const MEDIUM_RISK_FROM = 0.5;

/** Poziom ryzyka z surowego score (stałe pasma, niezależne od progu). */
export function riskLevel(score: number): RiskLevel {
  if (score >= HIGH_RISK_FROM) return "high";
  if (score >= MEDIUM_RISK_FROM) return "medium";
  return "low";
}

export function clampThreshold(v: number): number {
  if (!Number.isFinite(v)) return DEFAULT_THRESHOLD;
  return Math.min(1, Math.max(0, Math.round(v * 100) / 100));
}

export interface Confusion {
  tp: number;
  fp: number;
  fn: number;
  tn: number;
  precision: number | null;
  recall: number | null;
  f1: number | null;
  labeled: number;
  flagged: number;
}

/** Macierz pomyłek na rekordach z etykietą referencyjną, dla danego progu. */
export function confusionAt(records: IncidentRecord[], threshold: ThresholdInput): Confusion {
  let tp = 0, fp = 0, fn = 0, tn = 0, flagged = 0;
  for (const r of records) {
    const predicted = isFlagged(r, threshold);
    if (predicted) flagged++;
    if (r.groundTruth === undefined) continue;
    if (predicted && r.groundTruth) tp++;
    else if (predicted && !r.groundTruth) fp++;
    else if (!predicted && r.groundTruth) fn++;
    else tn++;
  }
  const precision = tp + fp > 0 ? tp / (tp + fp) : null;
  const recall = tp + fn > 0 ? tp / (tp + fn) : null;
  const f1 = precision !== null && recall !== null && precision + recall > 0 ? (2 * precision * recall) / (precision + recall) : null;
  return { tp, fp, fn, tn, precision, recall, f1, labeled: tp + fp + fn + tn, flagged };
}

/** Krzywa precision/recall dla wykresu kalibracji (przesuwa próg globalny; nadpisania per reguła pomija). */
export function sweep(records: IncidentRecord[], steps = 20) {
  return Array.from({ length: steps + 1 }, (_, i) => {
    const t = i / steps;
    const c = confusionAt(records, t);
    return { threshold: t, ...c };
  });
}
