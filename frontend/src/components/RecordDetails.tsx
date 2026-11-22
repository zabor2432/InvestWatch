import { ExternalLink, X } from "lucide-react";
import type { ThresholdInput } from "../domain/thresholds";
import { useMemo } from "react";
import { ENTITY_LABEL, MODULE_LABEL, STATUS_LABEL, STATUSES, VARIANT_LABEL } from "../domain/labels";
import { factorsOf } from "../domain/factors";
import type { IncidentRecord, RecordStatus } from "../domain/types";
import { useAnnotation } from "../hooks/useAnnotation";
import { usePersistedState } from "../hooks/usePersistedState";
import { fmtDateTime, isImagePreview } from "../lib/format";
import { RiskBadge } from "./RiskBadge";
import { AnnotationCard } from "./AnnotationCard";
import { Button } from "./ui/Button";
import { cn } from "./ui/cn";

interface Props {
  record: IncidentRecord;
  blind: boolean;
  threshold: ThresholdInput;
  history: IncidentRecord[];
  onOpenRecord: (id: string) => void;
  onStatusChange: (status: RecordStatus) => void;
  onClose: () => void;
}

const Field = ({ label, children }: { label: string; children: React.ReactNode }) => (
  <div>
    <dt className="text-xs text-muted">{label}</dt>
    <dd className="break-words">{children}</dd>
  </div>
);

export function RecordDetails({ record: r, blind, threshold, history, onOpenRecord, onStatusChange, onClose }: Props) {
  const [annotator, setAnnotator] = usePersistedState("iw.annotator", "");
  const ann = useAnnotation(r.id, annotator);
  const factors = useMemo(() => factorsOf(r, threshold), [r, threshold]);
  const revealed = !blind || ann.submitted !== null; // tryb ślepy: model ukryty do zatwierdzenia oceny
  const shots = (focus: "page" | "risk") => r.images.filter((i) => i.focus === focus);
  return (
    <article className="flex h-full flex-col" aria-label={`Szczegóły rekordu ${r.id}`}>
      <header className="flex items-start gap-2 border-b border-line p-3">
        <div className="min-w-0 flex-1">
          <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-muted">
            <span className="font-mono">{r.id}</span>
            <span>{MODULE_LABEL[r.module]}</span>
            {r.manipulated && <span className="rounded border border-risk-mid/50 bg-risk-mid/10 px-1.5 py-0.5 text-xs text-risk-mid" title={`Kontrolowany wariant testowy: materiał celowo zmodyfikowany${r.manipulatedRules ? `, celowo złamane reguły: ${r.manipulatedRules.join(", ")}` : ""}`}>zmanipulowany</span>}
            {revealed ? <RiskBadge score={r.score} /> : <span className="rounded border border-line px-1.5 py-0.5 text-xs">Ryzyko ukryte</span>}
          </div>
          <h2 className="text-base font-semibold leading-snug">{r.title}</h2>
        </div>
        <Button variant="ghost" size="sm" onClick={onClose} aria-label="Zamknij szczegóły (Esc)">
          <X className="h-4 w-4" aria-hidden />
        </Button>
      </header>

      <div className="flex-1 space-y-4 overflow-y-auto p-3">
        <section aria-label="Status rekordu">
          <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted">Status</h3>
          <div className="flex flex-wrap gap-1" role="group">
            {STATUSES.map((s, i) => (
              <button
                key={s}
                type="button"
                aria-pressed={r.status === s}
                onClick={() => onStatusChange(s)}
                className={cn("inline-flex h-8 items-center gap-1.5 rounded border px-2.5 text-sm", r.status === s ? "border-accent bg-accent text-bg" : "border-line bg-surface hover:bg-raised")}
              >
                {STATUS_LABEL[s]} <kbd className={r.status === s ? "border-bg/40 bg-transparent text-bg" : ""}>{i + 1}</kbd>
              </button>
            ))}
          </div>
        </section>

        <dl className="grid grid-cols-2 gap-x-4 gap-y-2">
          <Field label="Podmiot">{r.entity.name}</Field>
          <Field label="Rodzaj podmiotu">{ENTITY_LABEL[r.entity.kind]}</Field>
          {r.advertisedFirm && <Field label="Reklamowana firma inwestycyjna">{r.advertisedFirm}</Field>}
          <Field label="Platforma">{r.source}</Field>
          {r.publishedAt && <Field label="Opublikowano">{fmtDateTime(r.publishedAt)}</Field>}
          <Field label="Zebrano">{fmtDateTime(r.detectedAt)}</Field>
          <div className="col-span-2">
            <dt className="text-xs text-muted">Lokalizacja (URL)</dt>
            <dd>
              <a href={r.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 break-all font-mono text-xs text-accent hover:underline">
                {r.url} <ExternalLink className="h-3 w-3 shrink-0" aria-hidden />
              </a>
            </dd>
          </div>
        </dl>

        {r.content && (
          <section aria-label="Treść">
            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">Treść</h3>
            <p className="rounded border border-line bg-raised/50 p-2 leading-relaxed">{r.content}</p>
          </section>
        )}

        {(["page", "risk"] as const).map((focus) =>
          shots(focus).length > 0 && (
            <section key={focus} aria-label={focus === "page" ? "Obrazy materiału" : "Blok z informacją o ryzyku"}>
              <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">{focus === "page" ? "Obrazy materiału" : "Blok z informacją o ryzyku"}</h3>
              <div className={cn("grid items-start gap-2", shots(focus).length > 1 && "grid-cols-2")}>
                {shots(focus).map((img) => (
                  <figure key={`${img.variant}-${img.focus}`}>
                    <a href={img.url} target="_blank" rel="noopener noreferrer" title="Otwórz w pełnym rozmiarze">
                      <img src={img.url} alt={`${VARIANT_LABEL[img.variant]}: ${r.title}`} loading="lazy" className="max-h-80 w-full rounded border border-line bg-raised/50 object-contain object-top" />
                    </a>
                    <figcaption className="mt-0.5 text-center text-xs text-muted">{VARIANT_LABEL[img.variant]}</figcaption>
                  </figure>
                ))}
              </div>
            </section>
          ),
        )}

        {history.length > 0 && (
          <section aria-label="Historia obserwacji">
            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">Historia obserwacji ({history.length})</h3>
            <ul className="divide-y divide-line/60 rounded border border-line">
              {history.map((h) => (
                <li key={h.id}>
                  <button type="button" onClick={() => onOpenRecord(h.id)} className="flex w-full items-center justify-between gap-3 px-2 py-1.5 text-left text-xs hover:bg-raised">
                    <span className="min-w-0 truncate">{h.title}</span>
                    <span className="shrink-0 text-muted">{fmtDateTime(h.publishedAt ?? h.detectedAt)}</span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}

        {r.matchedPhrases && r.matchedPhrases.length > 0 && (
          <section aria-label="Wykryte frazy">
            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">Wykryte frazy</h3>
            <ul className="flex flex-wrap gap-1">
              {r.matchedPhrases.map((p) => (
                <li key={p} className="rounded border border-risk-mid/40 bg-risk-mid/10 px-1.5 py-0.5 text-xs text-risk-mid">{p}</li>
              ))}
            </ul>
          </section>
        )}

        {factors.length > 0 && (
          <AnnotationCard
            factors={factors}
            draft={ann.draft}
            submitted={ann.submitted}
            revealed={revealed}
            blind={blind}
            annotator={annotator}
            saving={ann.saving}
            error={ann.error}
            onAnnotator={setAnnotator}
            onAnswer={ann.setAnswer}
            onSubmit={(name) => void ann.submit(name, factors.map((f) => f.id))}
          />
        )}

        <section aria-label="Dowody">
          <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">Dowody</h3>
          <ul className="divide-y divide-line/60 rounded border border-line">
            {r.evidence.filter((e) => !isImagePreview(e)).map((e, i) => (
              <li key={`${e.kind}-${i}`} className="flex justify-between gap-3 px-2 py-1 text-xs">
                <span className="text-muted">{e.label}</span>
                <span className="break-all font-mono">{e.value}</span>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </article>
  );
}
