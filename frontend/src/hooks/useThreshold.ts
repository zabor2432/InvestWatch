import { useCallback, useState } from "react";
import { clampThreshold, DEFAULT_THRESHOLD } from "../domain/risk";
import type { Thresholds } from "../domain/thresholds";

const KEY = "iw.thresholds";
const DEFAULTS: Thresholds = { global: DEFAULT_THRESHOLD, rules: {} };

function load(): Thresholds {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) ?? "null") as Partial<Thresholds> | null;
    if (!raw) return DEFAULTS;
    const rules = Object.fromEntries(Object.entries(raw.rules ?? {}).map(([k, v]) => [k, clampThreshold(Number(v))]));
    return { global: clampThreshold(Number(raw.global ?? DEFAULT_THRESHOLD)), rules };
  } catch { return DEFAULTS; }
}

/** Próg globalny i nadpisania per reguła modułu 2 (zapamiętane w przeglądarce; wszystko liczone przy odczycie). */
export function useThreshold() {
  const [thresholds, setRaw] = useState<Thresholds>(load);
  const update = useCallback((fn: (t: Thresholds) => Thresholds) => {
    setRaw((prev) => {
      const next = fn(prev);
      try { localStorage.setItem(KEY, JSON.stringify(next)); } catch { /* brak storage */ }
      return next;
    });
  }, []);
  return {
    thresholds,
    setGlobal: (v: number) => update((t) => ({ ...t, global: clampThreshold(v) })),
    /** Próg jednej reguły; `null` usuwa nadpisanie (reguła wraca do progu globalnego). */
    setRule: (rule: string, v: number | null) =>
      update((t) => {
        const { [rule]: _drop, ...rest } = t.rules;
        return { ...t, rules: v === null ? rest : { ...rest, [rule]: clampThreshold(v) } };
      }),
    setRules: (rules: Record<string, number>) => update((t) => ({ ...t, rules: { ...t.rules, ...rules } })),
    resetRules: () => update((t) => ({ ...t, rules: {} })),
    reset: () => update(() => DEFAULTS),
  };
}
