import type { RefObject } from "react";
import { FiltersBar } from "../components/FiltersBar";
import { RecordDetails } from "../components/RecordDetails";
import { RecordsTable } from "../components/RecordsTable";
import { cn } from "../components/ui/cn";
import type { ThresholdInput } from "../domain/thresholds";
import type { Filters, IncidentRecord, RecordStatus } from "../domain/types";

interface Props {
  records: IncidentRecord[];
  total: number;
  filters: Filters;
  activeFilters: number;
  loading: boolean;
  error: string | null;
  selected: IncidentRecord | null;
  /** Pozostałe materiały tej samej pary (podmiot, firma) */
  history: IncidentRecord[];
  blind: boolean;
  threshold: ThresholdInput;
  searchRef: RefObject<HTMLInputElement>;
  onFilters: (p: Partial<Filters>) => void;
  onResetFilters: () => void;
  onSelect: (id: string | null) => void;
  onStatus: (id: string, s: RecordStatus) => void;
  onRetry: () => void;
}

export function ResultsPage(p: Props) {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="border-b border-line bg-surface px-4 py-2">
        <FiltersBar filters={p.filters} activeCount={p.activeFilters} searchRef={p.searchRef} onChange={p.onFilters} onReset={p.onResetFilters} />
        <div className="mt-1.5 text-xs text-muted" aria-live="polite">
          Wyświetlono <b className="text-fg">{p.records.length}</b> z {p.total} rekordów · <kbd>j</kbd>/<kbd>k</kbd> nawigacja · <kbd>/</kbd> szukaj · <kbd>1</kbd>–<kbd>4</kbd> status · <kbd>Esc</kbd> zamknij · <kbd>n</kbd> powiadomienia
        </div>
      </div>
      <div className="flex min-h-0 flex-1">
        <section className={cn("min-w-0 flex-1 bg-surface", p.selected && "hidden lg:block")} aria-label="Lista wyników">
          <RecordsTable blind={p.blind} records={p.records} selectedId={p.selected?.id ?? null} loading={p.loading} error={p.error} onSelect={p.onSelect} onRetry={p.onRetry} />
        </section>
        {p.selected && (
          <aside className="w-full shrink-0 border-l border-line bg-surface lg:w-[34rem]">
            <RecordDetails key={p.selected.id} record={p.selected} blind={p.blind} threshold={p.threshold} history={p.history} onOpenRecord={p.onSelect} onStatusChange={(s) => p.onStatus(p.selected!.id, s)} onClose={() => p.onSelect(null)} />
          </aside>
        )}
      </div>
    </div>
  );
}
