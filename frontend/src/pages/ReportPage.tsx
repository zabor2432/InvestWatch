import { Download } from "lucide-react";
import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card } from "../components/KpiCards";
import { MultiSelect } from "../components/ui/MultiSelect";
import { cn } from "../components/ui/cn";
import { factorName } from "../domain/factors";
import { MODULE_LABEL, MODULES } from "../domain/labels";
import { thresholdFor, type ThresholdInput } from "../domain/thresholds";
import { deviations, filterJudgments, histogram, interAnnotator, perAnnotator, perFactor, stats } from "../domain/report";
import type { IncidentRecord, ModuleId } from "../domain/types";
import { useReport } from "../hooks/useReport";
import { fmtPct, fmtScore } from "../lib/format";

const AXIS = { fontSize: 11, fill: "rgb(var(--muted))" };
const TOOLTIP = { contentStyle: { background: "rgb(var(--surface))", border: "1px solid rgb(var(--line))", borderRadius: 4, fontSize: 12 }, labelStyle: { color: "rgb(var(--fg))" }, itemStyle: { color: "rgb(var(--fg))" }, cursor: { fill: "rgb(var(--raised))" } };
const num = (v: number | null, d = 2) => (v === null ? "—" : v.toFixed(d));
const SELECT = "h-8 rounded border border-line bg-surface px-2 text-sm";
const TH = "border-b border-line px-2 py-1.5 text-left text-xs font-semibold uppercase tracking-wide text-muted";
const TD = "px-2 py-1.5";

interface Props {
  records: IncidentRecord[];
  threshold: ThresholdInput;
  onOpenRecord: (id: string) => void;
}

export function ReportPage({ records, threshold, onOpenRecord }: Props) {
  const [model, setModel] = useState<string | undefined>();
  const [module, setModule] = useState<ModuleId | "all">("all");
  const [annotators, setAnnotators] = useState<string[]>([]);
  const [factorKey, setFactorKey] = useState<string | null>(null);
  const { report, loading, error } = useReport(model);

  const js = useMemo(() => filterJudgments(report?.judgments ?? [], { module, annotators }), [report, module, annotators]);
  const overall = useMemo(() => stats(js, threshold), [js, threshold]);
  const rows = useMemo(() => perFactor(js, threshold), [js, threshold]);
  const byAnnotator = useMemo(() => perAnnotator(js, threshold), [js, threshold]);
  const devs = useMemo(() => deviations(js, threshold), [js, threshold]);
  const inter = useMemo(() => interAnnotator(js), [js]);
  const byId = useMemo(() => new Map(records.map((r) => [r.id, r])), [records]);

  const keyOf = (r: { module: number; factor: string }) => `${r.module}|${r.factor}`;
  const selected = rows.find((r) => keyOf(r) === factorKey) ?? [...rows].sort((a, b) => b.n - a.n)[0];
  const hist = useMemo(() => (selected ? histogram(js.filter((j) => j.module === selected.module && j.factor === selected.factor)) : []), [js, selected]);
  const selectedThreshold = selected ? thresholdFor(threshold, selected.module, selected.factor) : 0;
  const thresholdBin = Math.min(0.9, Math.floor(selectedThreshold * 10) / 10).toFixed(1);
  const label = (id: string) => byId.get(id)?.entity.name ?? `rekord ${id}`;

  const exportCsv = () => {
    const lines = ["record_id,module,annotator,factor,human,model_score", ...js.map((j) => [j.recordId, j.module, j.annotator, j.factor, j.human ?? "", j.score ?? ""].join(","))];
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([lines.join("\n")], { type: "text/csv" }));
    a.download = `raport-${report?.model ?? "model"}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  if (error) return <p className="p-8 text-center text-muted" role="alert">{error}</p>;
  if (!loading && (report?.judgments.length ?? 0) === 0) {
    return <p className="mx-auto max-w-xl p-10 text-center text-muted">Brak ocen ręcznych dla {report?.model ? <>modelu <b className="text-fg">{report.model}</b></> : "tego modelu"}. Oceń rekordy w widoku „Wyniki” (karta „Ocena ręczna”), a raport pojawi się tutaj.</p>;
  }

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-5" aria-busy={loading}>
      <div className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-1.5 text-xs text-muted">Model
          <select className={SELECT} value={report?.model ?? ""} onChange={(e) => setModel(e.target.value)}>
            {(report?.models ?? []).map((m) => <option key={m.model} value={m.model}>{m.model} ({m.results})</option>)}
          </select>
        </label>
        <label className="flex items-center gap-1.5 text-xs text-muted">Moduł
          <select className={SELECT} value={module} onChange={(e) => setModule(e.target.value === "all" ? "all" : (Number(e.target.value) as ModuleId))}>
            <option value="all">Wszystkie</option>
            {MODULES.map((m) => <option key={m} value={m}>{MODULE_LABEL[m]}</option>)}
          </select>
        </label>
        <MultiSelect label="Oceniający" options={report?.annotators ?? []} selected={annotators} getLabel={(a) => a} onChange={setAnnotators} />
        <span className="text-xs text-muted">Progi decyzji: globalny i per reguła z panelu Kalibracja</span>
        <button type="button" onClick={exportCsv} className="ml-auto inline-flex h-8 items-center gap-1.5 rounded border border-line bg-surface px-2.5 text-sm hover:bg-raised"><Download className="h-3.5 w-3.5" aria-hidden /> CSV</button>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5" role="group" aria-label="Wskaźniki raportu">
        <Card label="Ocenione rekordy" value={new Set(js.map((j) => j.recordId)).size}>{js.length} ocen czynników</Card>
        <Card label="Zgodność z modelem" value={fmtPct(overall.agreement)} tone={overall.agreement !== null && overall.agreement < 0.7 ? "text-risk-high" : undefined}>{overall.n} porównywalnych · kappa {num(overall.kappa)}</Card>
        <Card label="Precision modelu" value={fmtPct(overall.precision)}>{overall.tp} trafnych z {overall.tp + overall.fp} oflagowanych</Card>
        <Card label="Recall modelu" value={fmtPct(overall.recall)}>{overall.tp} wykrytych z {overall.tp + overall.fn} naruszeń</Card>
        <Card label="Zgodność oceniających" value={fmtPct(inter.agreement)}>{inter.shared} wspólnie ocenionych · {inter.conflicts.length} konfliktów</Card>
      </div>

      <section className="rounded border border-line bg-surface p-4" aria-label="Zgodność per czynnik">
        <h2 className="font-semibold">Zgodność modelu z oceną ręczną per czynnik</h2>
        <p className="mb-2 text-xs text-muted">Udział ocen, w których werdykt modelu (score ≥ próg) zgadza się z człowiekiem; M1/M3 to jedyny czynnik modułu, brak słupka = brak porównywalnych ocen (np. reguła 8). Kliknij wiersz tabeli, aby zobaczyć rozkład score.</p>
        <div className="h-60" role="img" aria-label="Wykres słupkowy zgodności per czynnik">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows.map((r) => ({ name: r.module === 2 ? r.factor : `M${r.module}`, zgodność: r.agreement === null ? undefined : Math.round(r.agreement * 100), n: r.n }))} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
              <CartesianGrid stroke="rgb(var(--line))" vertical={false} />
              <XAxis dataKey="name" tick={AXIS} tickLine={false} axisLine={{ stroke: "rgb(var(--line))" }} interval={0} />
              <YAxis domain={[0, 100]} unit="%" tick={AXIS} tickLine={false} axisLine={false} />
              <Tooltip {...TOOLTIP} formatter={(v, _n, p) => [`${v}% (n=${p.payload.n})`, "Zgodność"]} />
              <Bar dataKey="zgodność" fill="rgb(var(--accent))" isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr><th className={TH}>Czynnik</th><th className={TH}>Moduł</th><th className={TH}>n</th><th className={TH}>Zgodność</th><th className={TH}>TP/FP/FN/TN</th><th className={TH}>Próg</th><th className={TH}>Precision</th><th className={TH}>Recall</th><th className={TH} title="Średni score modelu: naruszenie wg człowieka">Śr. score (narusza)</th><th className={TH} title="Średni score modelu: zgodne wg człowieka">Śr. score (zgodne)</th><th className={TH} title="Najwyższy score na zgodnych: próg powyżej tej wartości nie daje fałszywych alarmów">Max score (zgodne)</th></tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={keyOf(r)} onClick={() => setFactorKey(keyOf(r))} className={cn("cursor-pointer border-b border-line/60 hover:bg-raised", selected && keyOf(selected) === keyOf(r) && "bg-accent/10")}>
                  <td className={TD}><span className="font-mono text-xs text-muted">{r.module === 2 ? r.factor : ""}</span> {factorName(r.factor)}</td>
                  <td className={TD}>M{r.module}</td><td className={TD}>{r.n}/{r.judgments}</td>
                  <td className={cn(TD, "font-mono", r.agreement !== null && r.agreement < 0.7 && "text-risk-high")}>{fmtPct(r.agreement)}</td>
                  <td className={cn(TD, "font-mono text-xs")}>{r.tp}/{r.fp}/{r.fn}/{r.tn}</td>
                  <td className={cn(TD, "font-mono")}>{thresholdFor(threshold, r.module, r.factor).toFixed(2)}</td><td className={cn(TD, "font-mono")}>{fmtPct(r.precision)}</td><td className={cn(TD, "font-mono")}>{fmtPct(r.recall)}</td>
                  <td className={cn(TD, "font-mono")}>{num(r.meanFlagged)}</td><td className={cn(TD, "font-mono")}>{num(r.meanOk)}</td><td className={cn(TD, "font-mono")}>{num(r.maxOk)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {selected && (
        <section className="rounded border border-line bg-surface p-4" aria-label="Rozkład score">
          <h2 className="font-semibold">Rozkład score modelu: {factorName(selected.factor)} <span className="text-xs font-normal text-muted">(M{selected.module}{selected.module === 2 ? `, reguła ${selected.factor}` : ""})</span></h2>
          <p className="mb-2 text-xs text-muted">Im lepiej oddzielone słupki „zgodne” (zielone) i „narusza” (czerwone), tym lepiej model rozróżnia. Linia = próg tego czynnika.</p>
          <div className="h-56" role="img" aria-label="Histogram score modelu według oceny ręcznej">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={hist} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
                <CartesianGrid stroke="rgb(var(--line))" vertical={false} />
                <XAxis dataKey="label" tick={AXIS} tickLine={false} axisLine={{ stroke: "rgb(var(--line))" }} />
                <YAxis allowDecimals={false} tick={AXIS} tickLine={false} axisLine={false} />
                <Tooltip {...TOOLTIP} labelFormatter={(l) => `score ${l}–${(Number(l) + 0.1).toFixed(1)}`} />
                <Legend iconType="square" wrapperStyle={{ fontSize: 12 }} />
                <ReferenceLine x={thresholdBin} stroke="rgb(var(--fg))" strokeDasharray="4 3" />
                <Bar dataKey="ok" name="Zgodne (człowiek)" stackId="a" fill="rgb(var(--risk-low))" isAnimationActive={false} />
                <Bar dataKey="flagged" name="Narusza (człowiek)" stackId="a" fill="rgb(var(--risk-high))" isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded border border-line bg-surface p-4" aria-label="Największe odchylenia">
          <h2 className="font-semibold">Największe odchylenia model vs człowiek</h2>
          <p className="mb-2 text-xs text-muted">Od najbardziej „pewnych” błędów modelu. Kliknij, aby otworzyć rekord.</p>
          {devs.length === 0 ? <p className="text-sm text-muted">Brak rozbieżności.</p> : (
            <table className="w-full text-sm">
              <thead><tr><th className={TH}>Rekord</th><th className={TH}>Czynnik</th><th className={TH}>Model</th><th className={TH}>Człowiek</th><th className={TH}>Kto</th></tr></thead>
              <tbody>
                {devs.map((d, i) => (
                  <tr key={i} onClick={() => onOpenRecord(d.recordId)} className="cursor-pointer border-b border-line/60 hover:bg-raised">
                    <td className={TD}>{label(d.recordId)} <span className="font-mono text-xs text-muted">#{d.recordId}</span></td>
                    <td className={TD}>{d.module === 2 ? d.factor : factorName(d.factor)}</td>
                    <td className={cn(TD, "font-mono")}>{fmtScore(d.score)}</td>
                    <td className={TD}>{d.human === 1 ? "✗ narusza" : "✓ zgodne"}</td><td className={TD}>{d.annotator}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className="space-y-4">
          <div className="rounded border border-line bg-surface p-4" aria-label="Oceniający">
            <h2 className="mb-2 font-semibold">Oceniający</h2>
            <table className="w-full text-sm">
              <thead><tr><th className={TH}>Osoba</th><th className={TH}>Ocen</th><th className={TH}>Zgodność z modelem</th></tr></thead>
              <tbody>{byAnnotator.map((a) => <tr key={a.annotator} className="border-b border-line/60"><td className={TD}>{a.annotator}</td><td className={cn(TD, "font-mono")}>{a.judgments}</td><td className={cn(TD, "font-mono")}>{fmtPct(a.agreement)} <span className="text-xs text-muted">(n={a.n})</span></td></tr>)}</tbody>
            </table>
          </div>
          <div className="rounded border border-line bg-surface p-4" aria-label="Konflikty między oceniającymi">
            <h2 className="mb-2 font-semibold">Konflikty między oceniającymi</h2>
            {inter.conflicts.length === 0 ? <p className="text-sm text-muted">Brak konfliktów{inter.shared === 0 && " (nie ma czynników ocenionych przez dwie osoby)"}.</p> : (
              <ul className="divide-y divide-line/60 text-sm">
                {inter.conflicts.slice(0, 10).map((c) => (
                  <li key={`${c.recordId}|${c.factor}`} onClick={() => onOpenRecord(c.recordId)} className="cursor-pointer py-1.5 hover:bg-raised">
                    {label(c.recordId)} <span className="font-mono text-xs text-muted">#{c.recordId}</span> · {c.module === 2 ? `reguła ${c.factor}` : factorName(c.factor)}:{" "}
                    {Object.entries(c.answers).map(([who, a]) => <span key={who} className="mr-2">{who} {a === 1 ? "✗" : a === 0 ? "✓" : "–"}</span>)}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
