import { useCallback, useEffect, useRef, useState } from "react";
import { api, type RefreshRun } from "../api";
import { debug } from "../lib/log";

const FINISHED = new Set(["SUCCESS", "FAILURE", "CANCELED"]);

export type RefreshResult = "success" | "failure" | "unavailable";

interface RunApi {
  start: () => Promise<RefreshRun>;
  status: (runId: string) => Promise<RefreshRun>;
}

/** Startuje run i odpytuje jego status do końca. Nie rzuca: błąd komunikacji to "unavailable". */
export async function watchRun(run: RunApi, pollMs: number, cancelled: () => boolean = () => false): Promise<RefreshResult | "cancelled"> {
  try {
    let current = await run.start();
    while (!FINISHED.has(current.status)) {
      await new Promise((r) => setTimeout(r, pollMs));
      if (cancelled()) return "cancelled";
      current = await run.status(current.runId);
    }
    return current.status === "SUCCESS" ? "success" : "failure";
  } catch (e) {
    debug("refresh", e);
    return "unavailable";
  }
}

/** Przycisk "Odśwież dane": uruchamia przetwarzanie w Dagsterze; `onDone` dostaje wynik. */
export function useRefresh(onDone: (result: RefreshResult) => void, pollMs = 2000) {
  const [refreshing, setRefreshing] = useState(false);
  const unmounted = useRef(false);
  useEffect(() => () => { unmounted.current = true; }, []);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    const result = await watchRun({ start: api.startRefresh, status: api.refreshStatus }, pollMs, () => unmounted.current);
    if (result === "cancelled") return;
    setRefreshing(false);
    onDone(result);
  }, [onDone, pollMs]);

  return { refreshing, refresh };
}
