import type { ReactNode } from "react";

export interface BreakdownRow {
  key: string;
  label: ReactNode;
  value: number;
  color: string;
}

export function Breakdown({ title, rows }: { title: string; rows: BreakdownRow[] }) {
  const total = rows.reduce((s, r) => s + r.value, 0);
  return (
    <section className="rounded border border-line bg-surface p-4" aria-label={title}>
      <h2 className="mb-3 font-semibold">{title}</h2>
      <ul className="space-y-2.5">
        {rows.map((r) => (
          <li key={r.key}>
            <div className="mb-1 flex justify-between text-xs">
              <span>{r.label}</span>
              <span className="font-mono text-muted">{r.value} · {total ? Math.round((r.value / total) * 100) : 0}%</span>
            </div>
            <div className="h-2 rounded bg-raised" role="presentation">
              <div className="h-2 rounded" style={{ width: `${total ? (r.value / total) * 100 : 0}%`, background: r.color }} />
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
