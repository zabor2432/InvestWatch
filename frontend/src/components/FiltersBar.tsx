import { Search, X } from "lucide-react";
import type { RefObject } from "react";
import { LEVEL_LABEL, LEVELS, MODULE_LABEL, MODULES, SOURCES, STATUS_LABEL, STATUSES } from "../domain/labels";
import type { Filters } from "../domain/types";
import { Button } from "./ui/Button";
import { MultiSelect } from "./ui/MultiSelect";

interface Props {
  filters: Filters;
  activeCount: number;
  searchRef: RefObject<HTMLInputElement>;
  onChange: (patch: Partial<Filters>) => void;
  onReset: () => void;
}

const dateCls = "h-8 rounded border border-line bg-surface px-2 text-sm";

export function FiltersBar({ filters, activeCount, searchRef, onChange, onReset }: Props) {
  return (
    <div className="flex flex-wrap items-center gap-2" role="search" aria-label="Filtry wyników">
      <label className="relative">
        <span className="sr-only">Szukaj</span>
        <Search className="pointer-events-none absolute left-2 top-2 h-4 w-4 text-muted" aria-hidden />
        <input
          ref={searchRef}
          value={filters.q}
          onChange={(e) => onChange({ q: e.target.value })}
          onKeyDown={(e) => { if (e.key === "Escape") e.currentTarget.blur(); }}
          placeholder="Szukaj podmiotu, treści, URL…"
          className="h-8 w-72 rounded border border-line bg-surface pl-8 pr-10 text-sm placeholder:text-muted"
        />
        <kbd className="absolute right-2 top-1.5">/</kbd>
      </label>
      <MultiSelect label="Moduł" options={MODULES} selected={filters.modules} getLabel={(m) => MODULE_LABEL[m]} onChange={(modules) => onChange({ modules })} />
      <MultiSelect label="Źródło" options={SOURCES} selected={filters.sources} getLabel={(s) => s} onChange={(sources) => onChange({ sources })} />
      <MultiSelect label="Ryzyko" options={LEVELS} selected={filters.levels} getLabel={(l) => LEVEL_LABEL[l]} onChange={(levels) => onChange({ levels })} />
      <MultiSelect label="Status" options={STATUSES} selected={filters.statuses} getLabel={(s) => STATUS_LABEL[s]} onChange={(statuses) => onChange({ statuses })} />
      <label className="flex items-center gap-1 text-xs text-muted">
        Od <input type="date" value={filters.from} max={filters.to || undefined} onChange={(e) => onChange({ from: e.target.value })} className={dateCls} />
      </label>
      <label className="flex items-center gap-1 text-xs text-muted">
        Do <input type="date" value={filters.to} min={filters.from || undefined} onChange={(e) => onChange({ to: e.target.value })} className={dateCls} />
      </label>
      {activeCount > 0 && (
        <Button variant="ghost" size="sm" onClick={onReset}>
          <X className="h-3.5 w-3.5" aria-hidden /> Wyczyść filtry ({activeCount})
        </Button>
      )}
    </div>
  );
}
