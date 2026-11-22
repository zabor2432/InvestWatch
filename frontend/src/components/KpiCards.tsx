import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import type { Kpis } from "../domain/stats";
import { fmtPct } from "../lib/format";

function Delta({ now, prev }: { now: number; prev: number }) {
  const d = now - prev;
  const Icon = d > 0 ? ArrowUpRight : d < 0 ? ArrowDownRight : Minus;
  return (
    <span className="inline-flex items-center gap-0.5 text-xs text-muted">
      <Icon className="h-3 w-3" aria-hidden />
      {d > 0 ? "+" : ""}{d} vs poprzednie 24 h
    </span>
  );
}

export const Card = ({ label, value, children, tone }: { label: string; value: string | number; children: React.ReactNode; tone?: string }) => (
  <div className="rounded border border-line bg-surface p-3">
    <div className="text-xs text-muted">{label}</div>
    <div className={`font-mono text-3xl font-semibold leading-tight ${tone ?? ""}`}>{value}</div>
    <div className="text-xs text-muted">{children}</div>
  </div>
);

export function KpiCards({ kpis }: { kpis: Kpis }) {
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-5" role="group" aria-label="Wskaźniki KPI">
      <Card label="Wykryte (powyżej progu)" value={kpis.total}>łącznie w bazie</Card>
      <Card label="Ostatnie 24 h" value={kpis.last24h}><Delta now={kpis.last24h} prev={kpis.prev24h} /></Card>
      <Card label="Wysokie ryzyko" value={kpis.high} tone="text-risk-high">score ≥ 0,80</Card>
      <Card label="Do weryfikacji" value={kpis.toReview} tone="text-risk-mid">nowe i w analizie</Card>
      <Card label="Trafność wykryć" value={fmtPct(kpis.confirmRate)}>{kpis.confirmed} potwierdzonych · {kpis.falsePositive} fałszywych</Card>
    </div>
  );
}
