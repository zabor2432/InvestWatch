import { flexRender, getCoreRowModel, getSortedRowModel, useReactTable, type ColumnDef, type SortingState } from "@tanstack/react-table";
import { ArrowDown, ArrowUp } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { MODULE_LABEL } from "../domain/labels";
import type { IncidentRecord } from "../domain/types";
import { fmtDateTime } from "../lib/format";
import { RiskBadge } from "./RiskBadge";
import { StatusBadge } from "./StatusBadge";
import { cn } from "./ui/cn";

interface Props {
  blind: boolean;
  records: IncidentRecord[];
  selectedId: string | null;
  loading: boolean;
  error: string | null;
  onSelect: (id: string) => void;
  onRetry: () => void;
}

const makeColumns = (blind: boolean): ColumnDef<IncidentRecord>[] => [
  { id: "detectedAt", header: "Wykryto", accessorFn: (r) => r.detectedAt, cell: (c) => <span className="whitespace-nowrap font-mono text-xs">{fmtDateTime(c.row.original.detectedAt)}</span>, size: 130 },
  { id: "module", header: "Moduł", accessorFn: (r) => r.module, cell: (c) => <span className="whitespace-nowrap text-xs">{MODULE_LABEL[c.row.original.module].split(" ")[0]}</span>, size: 56 },
  { id: "entity", header: "Podmiot / tytuł", accessorFn: (r) => r.entity.name, cell: (c) => (
      <div className="min-w-0">
        <div className="truncate font-medium">{c.row.original.entity.name}</div>
        <div className="truncate text-xs text-muted">{c.row.original.title}</div>
      </div>
    ), size: 320 },
  { id: "source", header: "Źródło", accessorFn: (r) => r.source, size: 90 },
  { id: "score", header: "Ryzyko", accessorFn: (r) => r.score, cell: (c) => (blind ? <span className="text-xs text-muted">ukryte</span> : <RiskBadge score={c.row.original.score} />), size: 130 },
  { id: "status", header: "Status", accessorFn: (r) => r.status, cell: (c) => <StatusBadge status={c.row.original.status} />, size: 120 },
];

export function RecordsTable({ blind, records, selectedId, loading, error, onSelect, onRetry }: Props) {
  const [sorting, setSorting] = useState<SortingState>([{ id: "detectedAt", desc: true }]);
  const data = useMemo(() => records, [records]);
  const columns = useMemo(() => makeColumns(blind), [blind]);
  const table = useReactTable({ data, columns, state: { sorting }, onSortingChange: setSorting, getCoreRowModel: getCoreRowModel(), getSortedRowModel: getSortedRowModel(), getRowId: (r) => r.id });
  const rows = table.getRowModel().rows;
  const bodyRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (selectedId) bodyRef.current?.querySelector(`[data-row-id="${CSS.escape(selectedId)}"]`)?.scrollIntoView({ block: "nearest" });
  }, [selectedId]);

  if (error) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-muted" role="alert">
        <p>{error}</p>
        <button type="button" onClick={onRetry} className="rounded border border-line bg-surface px-3 py-1 text-fg hover:bg-raised">Spróbuj ponownie</button>
      </div>
    );
  }

  return (
    <div ref={bodyRef} className="h-full overflow-auto" aria-busy={loading}>
      <table className="w-full table-fixed border-separate border-spacing-0 text-sm">
        <thead className="sticky top-0 z-10 bg-raised">
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id}>
              {hg.headers.map((h) => {
                const dir = h.column.getIsSorted();
                return (
                  <th key={h.id} style={{ width: h.getSize() }} aria-sort={dir === "asc" ? "ascending" : dir === "desc" ? "descending" : "none"} className="border-b border-line px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-muted">
                    <button type="button" onClick={h.column.getToggleSortingHandler()} className="inline-flex items-center gap-1 hover:text-fg">
                      {flexRender(h.column.columnDef.header, h.getContext())}
                      {dir === "asc" && <ArrowUp className="h-3 w-3" aria-hidden />}
                      {dir === "desc" && <ArrowDown className="h-3 w-3" aria-hidden />}
                    </button>
                  </th>
                );
              })}
            </tr>
          ))}
        </thead>
        <tbody>
          {rows.map((row) => {
            const selected = row.id === selectedId;
            return (
              <tr
                key={row.id}
                data-row-id={row.id}
                aria-selected={selected}
                onClick={() => onSelect(row.id)}
                className={cn("cursor-pointer", selected ? "bg-accent/15" : "hover:bg-raised/60")}
              >
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className={cn("border-b border-line/60 px-3 py-1.5 align-middle", selected && "first:shadow-[inset_3px_0_0_rgb(var(--accent))]")}>
                    {flexRender(cell.column.columnDef.cell ?? ((c) => String(c.getValue())), cell.getContext())}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
      {!loading && rows.length === 0 && <p className="p-8 text-center text-muted">Brak wyników dla bieżących filtrów i progu.</p>}
      {loading && rows.length === 0 && <p className="p-8 text-center text-muted">Ładowanie…</p>}
    </div>
  );
}
