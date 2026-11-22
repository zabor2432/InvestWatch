import type { Filters, IncidentRecord } from "./types";
import { riskLevel } from "./risk";
import { isFlagged, type ThresholdInput } from "./thresholds";

export const EMPTY_FILTERS: Filters = { q: "", modules: [], sources: [], levels: [], statuses: [], from: "", to: "" };

export function applyFilters(records: IncidentRecord[], f: Filters, threshold: ThresholdInput): IncidentRecord[] {
  const q = f.q.trim().toLowerCase();
  const from = f.from ? new Date(f.from + "T00:00:00").getTime() : -Infinity;
  const to = f.to ? new Date(f.to + "T23:59:59.999").getTime() : Infinity;
  return records.filter((r) => {
    if (!isFlagged(r, threshold)) return false;
    if (f.modules.length && !f.modules.includes(r.module)) return false;
    if (f.sources.length && !f.sources.includes(r.source)) return false;
    if (f.levels.length && !f.levels.includes(riskLevel(r.score))) return false;
    if (f.statuses.length && !f.statuses.includes(r.status)) return false;
    const t = new Date(r.detectedAt).getTime();
    if (t < from || t > to) return false;
    if (q && !`${r.title} ${r.entity.name} ${r.advertisedFirm ?? ""} ${r.url} ${r.content}`.toLowerCase().includes(q)) return false;
    return true;
  });
}

export function activeFilterCount(f: Filters): number {
  return (f.q ? 1 : 0) + (f.modules.length ? 1 : 0) + (f.sources.length ? 1 : 0) + (f.levels.length ? 1 : 0) + (f.statuses.length ? 1 : 0) + (f.from ? 1 : 0) + (f.to ? 1 : 0);
}
