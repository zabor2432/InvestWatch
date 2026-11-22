import * as Slider from "@radix-ui/react-slider";
import { RotateCcw } from "lucide-react";
import { useMemo } from "react";
import { DEFAULT_THRESHOLD, confusionAt, sweep } from "../domain/risk";
import type { Thresholds } from "../domain/thresholds";
import type { IncidentRecord } from "../domain/types";
import { fmtPct } from "../lib/format";
import { Button } from "./ui/Button";
import { RuleThresholds } from "./RuleThresholds";

interface Props {
  records: IncidentRecord[];
  thresholds: Thresholds;
  onGlobal: (v: number) => void;
  onRule: (rule: string, v: number | null) => void;
  onRules: (rules: Record<string, number>) => void;
  onResetRules: () => void;
  onReset: () => void;
}

const Stat = ({ label, value, hint, tone }: { label: string; value: string | number; hint: string; tone?: string }) => (
  <div className="rounded border border-line bg-surface p-3">
    <div className="text-xs text-muted">{label}</div>
    <div className={`font-mono text-2xl font-semibold ${tone ?? ""}`}>{value}</div>
    <div className="text-xs text-muted">{hint}</div>
  </div>
);

function Curve({ points, threshold }: { points: ReturnType<typeof sweep>; threshold: number }) {
  const W = 560, H = 200, P = 28;
  const x = (t: number) => P + t * (W - 2 * P);
  const y = (v: number) => H - P - v * (H - 2 * P);
  const line = (key: "precision" | "recall") =>
    points.filter((p) => p[key] !== null).map((p, i) => `${i ? "L" : "M"}${x(p.threshold).toFixed(1)},${y(p[key] as number).toFixed(1)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Precision i recall w funkcji progu">
      {[0, 0.25, 0.5, 0.75, 1].map((g) => (
        <g key={g}>
          <line x1={P} x2={W - P} y1={y(g)} y2={y(g)} stroke="rgb(var(--line))" />
          <text x={P - 4} y={y(g) + 4} textAnchor="end" fontSize="10" fill="rgb(var(--muted))">{g * 100}%</text>
          <text x={x(g)} y={H - 10} textAnchor="middle" fontSize="10" fill="rgb(var(--muted))">{g.toFixed(2)}</text>
        </g>
      ))}
      <path d={line("precision")} fill="none" stroke="rgb(var(--accent))" strokeWidth="2" />
      <path d={line("recall")} fill="none" stroke="rgb(var(--risk-mid))" strokeWidth="2" strokeDasharray="5 3" />
      <line x1={x(threshold)} x2={x(threshold)} y1={P - 8} y2={H - P} stroke="rgb(var(--risk-high))" strokeWidth="1.5" />
    </svg>
  );
}

export function CalibrationPanel({ records, thresholds, onGlobal: onChange, onRule, onRules, onResetRules, onReset }: Props) {
  const threshold = thresholds.global;
  const c = useMemo(() => confusionAt(records, thresholds), [records, thresholds]);
  const curve = useMemo(() => sweep(records, 20), [records]);
  return (
    <div className="mx-auto max-w-5xl space-y-5 p-5">
      <div>
        <h2 className="text-lg font-semibold">Kalibracja progu detekcji</h2>
        <p className="text-muted">
          Rekord trafia na listę, gdy jego score ≥ próg (w module 2: gdy którakolwiek reguła przekracza własny próg, poniżej). Podniesienie progu zmniejsza liczbę fałszywych alarmów (FP), ale zwiększa liczbę pominięć (FN). Obliczenia na {c.labeled} rekordach z etykietą referencyjną (dane symulowane).
        </p>
      </div>

      <div className="rounded border border-line bg-surface p-4">
        <div className="mb-3 flex items-center justify-between">
          <label htmlFor="thr" className="font-medium">Próg (threshold)</label>
          <div className="flex items-center gap-2">
            <input
              id="thr"
              type="number"
              min={0}
              max={1}
              step={0.01}
              value={threshold}
              onChange={(e) => onChange(Number(e.target.value))}
              className="h-8 w-20 rounded border border-line bg-bg px-2 text-right font-mono"
            />
            <Button size="sm" onClick={onReset} disabled={threshold === DEFAULT_THRESHOLD}>
              <RotateCcw className="h-3.5 w-3.5" aria-hidden /> Domyślny ({DEFAULT_THRESHOLD})
            </Button>
          </div>
        </div>
        <Slider.Root className="relative flex h-5 w-full touch-none select-none items-center" min={0} max={1} step={0.01} value={[threshold]} onValueChange={([v]) => onChange(v)} aria-label="Próg detekcji">
          <Slider.Track className="relative h-1.5 grow rounded-full bg-raised">
            <Slider.Range className="absolute h-full rounded-full bg-accent" />
          </Slider.Track>
          <Slider.Thumb className="block h-4 w-4 rounded-full border-2 border-accent bg-surface shadow" />
        </Slider.Root>
        <div className="mt-1 flex justify-between text-xs text-muted"><span>0,00 (flaguj wszystko)</span><span>1,00 (flaguj nic)</span></div>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Flagowane" value={c.flagged} hint="rekordów powyżej progu" />
        <Stat label="False Positive" value={c.fp} hint="fałszywe alarmy" tone="text-risk-mid" />
        <Stat label="False Negative" value={c.fn} hint="pominięte naruszenia" tone="text-risk-high" />
        <Stat label="True Positive" value={c.tp} hint="trafne wykrycia" tone="text-risk-low" />
        <Stat label="Precision" value={fmtPct(c.precision)} hint="TP / (TP + FP)" />
        <Stat label="Recall" value={fmtPct(c.recall)} hint="TP / (TP + FN)" />
        <Stat label="F1" value={fmtPct(c.f1)} hint="średnia harmoniczna" />
        <Stat label="True Negative" value={c.tn} hint="poprawnie pominięte" />
      </div>

      <div className="rounded border border-line bg-surface p-4">
        <div className="mb-2 flex gap-4 text-xs">
          <span className="flex items-center gap-1.5"><span className="h-0.5 w-5 bg-accent" /> Precision</span>
          <span className="flex items-center gap-1.5"><span className="h-0.5 w-5 border-t-2 border-dashed border-risk-mid" /> Recall</span>
          <span className="flex items-center gap-1.5"><span className="h-3 w-0.5 bg-risk-high" /> Bieżący próg</span>
        </div>
        <Curve points={curve} threshold={threshold} />
      </div>

      <RuleThresholds thresholds={thresholds} onRule={onRule} onRules={onRules} onReset={onResetRules} />
    </div>
  );
}
