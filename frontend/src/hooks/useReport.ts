import { useEffect, useState } from "react";
import { api } from "../api";
import type { Report } from "../domain/types";
import { debug } from "../lib/log";

/** Raport odchyleń dla wybranego modelu (bez modelu: ten z największą liczbą wyników). Odświeżany przy wejściu w widok. */
export function useReport(model: string | undefined) {
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    setLoading(true);
    api.report(model)
      .then((r) => { if (live) { setReport(r); setError(null); } })
      .catch((e: unknown) => { debug("report", e); if (live) setError("Nie udało się pobrać raportu."); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [model]);

  return { report, loading, error };
}
