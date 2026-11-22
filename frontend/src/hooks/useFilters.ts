import { useCallback, useEffect, useState } from "react";
import { EMPTY_FILTERS } from "../domain/filters";
import { LEVELS, MODULES, SOURCES, STATUSES } from "../domain/labels";
import type { Filters } from "../domain/types";

const list = <T extends string | number>(raw: string | null, allowed: readonly T[]): T[] =>
  (raw ? raw.split(",") : []).map((v) => allowed.find((a) => String(a) === v)).filter((v): v is T => v !== undefined);

export function parseFilters(search: string): Filters {
  const p = new URLSearchParams(search);
  return {
    q: p.get("q") ?? "",
    modules: list(p.get("m"), MODULES),
    sources: list(p.get("s"), SOURCES),
    levels: list(p.get("r"), LEVELS),
    statuses: list(p.get("st"), STATUSES),
    from: p.get("from") ?? "",
    to: p.get("to") ?? "",
  };
}

export function serializeFilters(f: Filters, existing = ""): string {
  const p = new URLSearchParams(existing);
  for (const k of ["q", "m", "s", "r", "st", "from", "to"]) p.delete(k);
  if (f.q) p.set("q", f.q);
  if (f.modules.length) p.set("m", f.modules.join(","));
  if (f.sources.length) p.set("s", f.sources.join(","));
  if (f.levels.length) p.set("r", f.levels.join(","));
  if (f.statuses.length) p.set("st", f.statuses.join(","));
  if (f.from) p.set("from", f.from);
  if (f.to) p.set("to", f.to);
  const s = p.toString();
  return s ? `?${s}` : "";
}

/** Filtry zsynchronizowane z URL (link do widoku można wkleić koledze). */
export function useFilters() {
  const [filters, setFilters] = useState<Filters>(() => parseFilters(location.search));

  useEffect(() => {
    const next = serializeFilters(filters, location.search);
    if (next !== location.search) history.replaceState(null, "", `${location.pathname}${next}${location.hash}`);
  }, [filters]);

  const patch = useCallback((p: Partial<Filters>) => setFilters((f) => ({ ...f, ...p })), []);
  const reset = useCallback(() => setFilters(EMPTY_FILTERS), []);
  return { filters, patch, reset };
}
