import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import type { IncidentRecord, RecordStatus } from "../domain/types";
import { debug } from "../lib/log";

export interface RecordsState {
  records: IncidentRecord[];
  loading: boolean;
  error: string | null;
  reload: () => void;
  /** Optymistyczna zmiana statusu; zwraca false i robi rollback przy błędzie. */
  updateStatus: (id: string, status: RecordStatus) => Promise<boolean>;
  prepend: (record: IncidentRecord) => void;
}

export function useRecords(): RecordsState {
  const [records, setRecords] = useState<IncidentRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    let live = true;
    setLoading(true);
    api.listRecords()
      .then((items) => { if (live) { setRecords(items); setError(null); } })
      .catch((e: unknown) => { debug("listRecords", e); if (live) setError("Nie udało się pobrać wyników."); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [nonce]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  const updateStatus = useCallback(async (id: string, status: RecordStatus) => {
    let previous: RecordStatus | undefined;
    setRecords((rs) => rs.map((r) => { if (r.id === id) { previous = r.status; return { ...r, status }; } return r; }));
    try {
      await api.updateStatus(id, status);
      return true;
    } catch (e) {
      debug("updateStatus", e);
      setRecords((rs) => rs.map((r) => (r.id === id && previous ? { ...r, status: previous } : r)));
      return false;
    }
  }, []);

  const prepend = useCallback((record: IncidentRecord) => {
    setRecords((rs) => (rs.some((r) => r.id === record.id) ? rs : [record, ...rs]));
  }, []);

  return { records, loading, error, reload, updateStatus, prepend };
}
