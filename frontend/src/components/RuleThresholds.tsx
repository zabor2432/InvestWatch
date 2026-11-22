import { Wand2 } from "lucide-react";
import { useMemo } from "react";
import { factorName } from "../domain/factors";
import { perFactor, stats } from "../domain/report";
import { suggestThreshold, thresholdFor, type Thresholds } from "../domain/thresholds";
import { useReport } from "../hooks/useReport";
import { fmtPct } from "../lib/format";
import { Button } from "./ui/Button";

interface Props {
  thresholds: Thresholds;
  onRule: (rule: string, v: number | null) => void;
  onRules: (rules: Record<string, number>) => void;
  onReset: () => void;
}

const TH = "border-b border-line px-2 py-1.5 text-left text-xs font-semibold uppercase tracking-wide text-muted";

/** Progi per reguła modułu 2. Sugestia = próg o najlepszym F1 względem ocen analityków (zakładka Raport pokazuje je szczegółowo). */
export function RuleThresholds({ thresholds, onRule, onRules, onReset }: Props) {
  const { report, loading } = useReport(undefined);
  const rows = useMemo(() => {
    const js = (report?.judgments ?? []).filter((j) => j.module === 2);
    return perFactor(js, thresholds).map((r) => {
      const own = js.filter((j) => j.factor === r.factor);
      const suggested = suggestThreshold(own);
      return { ...r, suggested, atSuggested: suggested === null ? null : stats(own, suggested).agreement, current: thresholdFor(thresholds, 2, r.factor) };
    });
  }, [report, thresholds]);
  const pending = rows.filter((r) => r.suggested !== null && r.suggested !== r.current);

  return (
    <section className="rounded border border-line bg-surface p-4" aria-label="Progi per reguła" aria-busy={loading}>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <h3 className="font-semibold">Progi per reguła (moduł 2)</h3>
        <span className="text-xs text-muted">Reguła bez własnego progu używa globalnego ({thresholds.global.toFixed(2)}).</span>
        <div className="ml-auto flex gap-2">
          <Button size="sm" disabled={pending.length === 0} onClick={() => onRules(Object.fromEntries(pending.map((r) => [r.factor, r.suggested as number])))}>
            <Wand2 className="h-3.5 w-3.5" aria-hidden /> Zastosuj sugestie ({pending.length})
          </Button>
          <Button size="sm" disabled={Object.keys(thresholds.rules).length === 0} onClick={onReset}>Usuń progi reguł</Button>
        </div>
      </div>
      {rows.length === 0 ? (
        <p className="text-sm text-muted">Brak ocen ręcznych reguł. Oceń rekordy modułu 2 w widoku „Wyniki”, a sugestie progów pojawią się tutaj.</p>
      ) : (
        <table className="w-full text-sm">
          <thead><tr><th className={TH}>Reguła</th><th className={TH}>Ocen</th><th className={TH}>Zgodność dziś</th><th className={TH}>Próg</th><th className={TH}>Sugestia</th><th className={TH}>Zgodność przy sugestii</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.factor} className="border-b border-line/60">
                <td className="px-2 py-1.5"><span className="font-mono text-xs text-muted">{r.factor}</span> {factorName(r.factor)}</td>
                <td className="px-2 py-1.5 font-mono">{r.n}</td>
                <td className="px-2 py-1.5 font-mono">{fmtPct(r.agreement)}</td>
                <td className="px-2 py-1.5">
                  <input type="number" min={0} max={1} step={0.05} value={r.current} aria-label={`Próg reguły ${r.factor}`} onChange={(e) => onRule(r.factor, Number(e.target.value))} className="h-7 w-20 rounded border border-line bg-bg px-2 text-right font-mono" />
                  {r.factor in thresholds.rules && <button type="button" onClick={() => onRule(r.factor, null)} className="ml-1 text-xs text-muted hover:underline" title="Wróć do progu globalnego">×</button>}
                </td>
                <td className="px-2 py-1.5 font-mono">{r.suggested === null ? <span className="text-xs text-muted">za mało ocen</span> : r.suggested.toFixed(2)}</td>
                <td className="px-2 py-1.5 font-mono">{fmtPct(r.atSuggested)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
