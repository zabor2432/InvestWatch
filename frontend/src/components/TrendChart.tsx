import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { MODULE_LABEL, MODULES } from "../domain/labels";
import type { DayPoint } from "../domain/stats";
import { cn } from "./ui/cn";

interface Props {
  data: DayPoint[];
  days: number;
  onDays: (d: number) => void;
}

const RANGES = [7, 14, 30];
const COLOR = { 1: "rgb(var(--c1))", 2: "rgb(var(--c2))", 3: "rgb(var(--c3))" } as const;
const AXIS = { fontSize: 11, fill: "rgb(var(--muted))" };

const shortDay = (iso: string) => `${iso.slice(8, 10)}.${iso.slice(5, 7)}`;

export function TrendChart({ data, days, onDays }: Props) {
  const total = data.reduce((s, d) => s + d.total, 0);
  return (
    <section className="rounded border border-line bg-surface p-4" aria-label="Trend liczby incydentów">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h2 className="font-semibold">Liczba wykrytych incydentów w czasie</h2>
          <p className="text-xs text-muted">{total} incydentów w ostatnich {days} dniach, według modułu</p>
        </div>
        <div className="flex gap-1" role="group" aria-label="Zakres czasu">
          {RANGES.map((r) => (
            <button key={r} type="button" aria-pressed={days === r} onClick={() => onDays(r)} className={cn("h-7 rounded border px-2 text-xs", days === r ? "border-accent bg-accent text-bg" : "border-line bg-surface hover:bg-raised")}>
              {r} dni
            </button>
          ))}
        </div>
      </div>
      <div className="h-72" role="img" aria-label={`Wykres słupkowy: ${total} incydentów w ostatnich ${days} dniach`}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
            <CartesianGrid stroke="rgb(var(--line))" vertical={false} />
            <XAxis dataKey="day" tickFormatter={shortDay} tick={AXIS} tickLine={false} axisLine={{ stroke: "rgb(var(--line))" }} interval="preserveStartEnd" minTickGap={16} />
            <YAxis allowDecimals={false} tick={AXIS} tickLine={false} axisLine={false} />
            <Tooltip
              cursor={{ fill: "rgb(var(--raised))" }}
              labelFormatter={(l) => String(l)}
              contentStyle={{ background: "rgb(var(--surface))", border: "1px solid rgb(var(--line))", borderRadius: 4, fontSize: 12 }}
              labelStyle={{ color: "rgb(var(--fg))" }}
              itemStyle={{ color: "rgb(var(--fg))" }}
            />
            <Legend iconType="square" wrapperStyle={{ fontSize: 12 }} />
            {MODULES.map((m) => (
              <Bar key={m} dataKey={String(m)} name={MODULE_LABEL[m]} stackId="a" fill={COLOR[m]} isAnimationActive={false} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
