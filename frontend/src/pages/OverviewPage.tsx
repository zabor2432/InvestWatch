import { useMemo, useState } from "react";
import { Breakdown } from "../components/Breakdown";
import { KpiCards } from "../components/KpiCards";
import { TrendChart } from "../components/TrendChart";
import { LEVEL_LABEL, LEVELS, MODULE_LABEL, MODULES } from "../domain/labels";
import { computeKpis, dailyTrend, perModule, riskDistribution } from "../domain/stats";
import { isFlagged, type ThresholdInput } from "../domain/thresholds";
import type { IncidentRecord } from "../domain/types";

const LEVEL_COLOR = { high: "rgb(var(--risk-high))", medium: "rgb(var(--risk-mid))", low: "rgb(var(--risk-low))" } as const;
const MODULE_COLOR = { 1: "rgb(var(--c1))", 2: "rgb(var(--c2))", 3: "rgb(var(--c3))" } as const;

/** Rekordy powyżej progu (te same, które trafiają na listę wyników). */
export function OverviewPage({ records, threshold }: { records: IncidentRecord[]; threshold: ThresholdInput }) {
  const [days, setDays] = useState(30);
  const flagged = useMemo(() => records.filter((r) => isFlagged(r, threshold)), [records, threshold]);
  const kpis = useMemo(() => computeKpis(flagged), [flagged]);
  const trend = useMemo(() => dailyTrend(flagged, days), [flagged, days]);
  const risk = useMemo(() => riskDistribution(flagged), [flagged]);
  const mods = useMemo(() => perModule(flagged), [flagged]);

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-5">
      <KpiCards kpis={kpis} />
      <TrendChart data={trend} days={days} onDays={setDays} />
      <div className="grid gap-4 md:grid-cols-2">
        <Breakdown title="Rozkład poziomów ryzyka" rows={LEVELS.map((l) => ({ key: l, label: LEVEL_LABEL[l], value: risk[l], color: LEVEL_COLOR[l] }))} />
        <Breakdown title="Incydenty według modułu" rows={MODULES.map((m) => ({ key: String(m), label: MODULE_LABEL[m], value: mods[m], color: MODULE_COLOR[m] }))} />
      </div>
    </div>
  );
}
