import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import type { Annotation, Answer } from "../domain/types";
import { debug } from "../lib/log";

export type Draft = Record<string, Answer | undefined>;

/** Ręczna ocena rekordu: szkic odpowiedzi, ostatnie zatwierdzenie tego oceniającego i zapis (nowy wpis przy każdym zatwierdzeniu). */
export function useAnnotation(recordId: string, annotator: string) {
  const [draft, setDraft] = useState<Draft>({});
  const [submitted, setSubmitted] = useState<Annotation | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { setDraft({}); setSubmitted(null); setError(null); }, [recordId]);

  useEffect(() => {
    let live = true;
    setSubmitted(null);
    if (!annotator) return;
    api.listAnnotations(recordId, annotator)
      .then((items) => {
        if (!live) return;
        setSubmitted(items[0] ?? null);
        if (items[0]) setDraft((d) => (Object.keys(d).length ? d : items[0].answers));
      })
      .catch((e: unknown) => { debug("listAnnotations", e); if (live) setError("Nie udało się pobrać wcześniejszej oceny."); });
    return () => { live = false; };
  }, [recordId, annotator]);

  const setAnswer = useCallback((id: string, v: Answer) => setDraft((d) => ({ ...d, [id]: v })), []);

  const submit = useCallback(async (name: string, factorIds: string[]) => {
    setSaving(true); setError(null);
    try {
      const answers = Object.fromEntries(factorIds.map((id) => [id, draft[id] ?? null])) as Record<string, Answer>;
      setSubmitted(await api.submitAnnotation(recordId, name, answers));
      return true;
    } catch (e) {
      debug("submitAnnotation", e);
      setError("Nie udało się zapisać oceny.");
      return false;
    } finally { setSaving(false); }
  }, [recordId, draft]);

  return { draft, setAnswer, submitted, saving, error, submit };
}
