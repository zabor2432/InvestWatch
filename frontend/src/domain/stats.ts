import { riskLevel } from "./risk";
import type { IncidentRecord, ModuleId, RiskLevel } from "./types";

export interface DayPoint {
  day: string; // YYYY-MM-DD (czas lokalny)
  1: number;
  2: number;
  3: number;
  total: number;
}

const dayKey = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

/** Liczba incydentów na dzień i moduł dla ostatnich `days` dni (włącznie z dziś), z zerami dla pustych dni. */
export function dailyTrend(records: IncidentRecord[], days: number, now = Date.now()): DayPoint[] {
  const map = new Map<string, DayPoint>();
  for (let i = days - 1; i >= 0; i--) {
    const k = dayKey(new Date(now - i * 86400000));
    map.set(k, { day: k, 1: 0, 2: 0, 3: 0, total: 0 });
  }
  for (const r of records) {
    const p = map.get(dayKey(new Date(r.detectedAt)));
    if (!p) continue;
    p[r.module]++;
    p.total++;
  }
  return [...map.values()];
}

export function riskDistribution(records: IncidentRecord[]): Record<RiskLevel, number> {
  const out: Record<RiskLevel, number> = { low: 0, medium: 0, high: 0 };
  for (const r of records) out[riskLevel(r.score)]++;
  return out;
}

export function perModule(records: IncidentRecord[]): Record<ModuleId, number> {
  const out: Record<ModuleId, number> = { 1: 0, 2: 0, 3: 0 };
  for (const r of records) out[r.module]++;
  return out;
}

export interface Kpis {
  total: number;
  last24h: number;
  prev24h: number;
  high: number;
  toReview: number;
  confirmed: number;
  falsePositive: number;
  /** Odsetek potwierdzonych wśród rozstrzygniętych (potwierdzony + fałszywy alarm); null gdy brak rozstrzygnięć. */
  confirmRate: number | null;
}

export function computeKpis(records: IncidentRecord[], now = Date.now()): Kpis {
  const k: Kpis = { total: records.length, last24h: 0, prev24h: 0, high: 0, toReview: 0, confirmed: 0, falsePositive: 0, confirmRate: null };
  for (const r of records) {
    const age = now - new Date(r.detectedAt).getTime();
    if (age >= 0 && age < 86400000) k.last24h++;
    else if (age >= 86400000 && age < 2 * 86400000) k.prev24h++;
    if (riskLevel(r.score) === "high") k.high++;
    if (r.status === "new" || r.status === "in_review") k.toReview++;
    if (r.status === "confirmed") k.confirmed++;
    if (r.status === "false_positive") k.falsePositive++;
  }
  const decided = k.confirmed + k.falsePositive;
  k.confirmRate = decided ? k.confirmed / decided : null;
  return k;
}
