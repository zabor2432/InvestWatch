import { useCallback, useState } from "react";

/** useState zapamiętywany w localStorage (JSON); bez storage działa jak zwykły stan. */
export function usePersistedState<T>(key: string, initial: T) {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = localStorage.getItem(key);
      return raw === null ? initial : (JSON.parse(raw) as T);
    } catch { return initial; }
  });
  const set = useCallback((v: T) => {
    setValue(v);
    try { localStorage.setItem(key, JSON.stringify(v)); } catch { /* brak storage */ }
  }, [key]);
  return [value, set] as const;
}
