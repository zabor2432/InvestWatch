import { Check, CircleHelp, EyeOff, Minus, X } from "lucide-react";
import { useState } from "react";
import { agreement, type Factor } from "../domain/factors";
import type { Annotation, Answer } from "../domain/types";
import type { Draft } from "../hooks/useAnnotation";
import { fmtDateTime, fmtScore } from "../lib/format";
import { Button } from "./ui/Button";
import { cn } from "./ui/cn";

interface Props {
  factors: Factor[];
  draft: Draft;
  submitted: Annotation | null;
  /** Odpowiedzi modelu widoczne (tryb ślepy wyłączony albo ocena już zatwierdzona). */
  revealed: boolean;
  blind: boolean;
  annotator: string;
  saving: boolean;
  error: string | null;
  onAnnotator: (name: string) => void;
  onAnswer: (id: string, v: Answer) => void;
  onSubmit: (name: string) => void;
}

function AnswerButtons({ f, value, onPick }: { f: Factor; value: Answer | undefined; onPick: (v: Answer) => void }) {
  const opt = (v: Answer, label: string, Icon: typeof Check, tone: string) => (
    <button
      type="button"
      aria-pressed={value === v}
      onClick={() => onPick(v)}
      className={cn("inline-flex h-7 items-center gap-1 rounded border px-1.5 text-xs", value === v ? tone : "border-line bg-surface text-muted hover:bg-raised")}
    >
      <Icon className="h-3 w-3" aria-hidden /> {label}
    </button>
  );
  return (
    <div className="flex flex-wrap gap-1" role="group" aria-label={`Ocena: ${f.name}`}>
      {opt(0, f.okLabel, Check, "border-risk-low bg-risk-low/15 text-risk-low")}
      {opt(1, f.flagLabel, X, "border-risk-high bg-risk-high/15 text-risk-high")}
      {opt(null, "Nie dotyczy", Minus, "border-line bg-raised text-fg")}
    </div>
  );
}

function ModelCell({ f, revealed }: { f: Factor; revealed: boolean }) {
  if (!revealed) return <span className="inline-flex items-center gap-1 text-xs text-muted"><EyeOff className="h-3 w-3" aria-hidden /> ukryte</span>;
  const a = f.model.answer;
  const Icon = a === 0 ? Check : a === 1 ? X : a === null ? Minus : CircleHelp;
  const tone = a === 0 ? "text-risk-low" : a === 1 ? "text-risk-high" : a === null ? "text-muted" : "text-risk-mid";
  return (
    <span className={cn("inline-flex items-center gap-1 whitespace-nowrap text-xs font-medium", tone)} title="Odpowiedź modelu">
      <Icon className="h-3.5 w-3.5" aria-hidden /> Model{f.model.score !== null && <span className="font-mono font-normal opacity-80">{fmtScore(f.model.score)}</span>}
    </span>
  );
}

export function AnnotationCard(p: Props) {
  const [name, setName] = useState(p.annotator);
  const answered = p.factors.filter((f) => p.draft[f.id] !== undefined).length;
  const complete = answered === p.factors.length && p.factors.length > 0;
  const { agree, comparable } = agreement(p.factors, p.draft);
  const commit = () => { if (name.trim() !== p.annotator) p.onAnnotator(name.trim()); };

  return (
    <section aria-label="Ocena ręczna">
      <div className="mb-2 flex flex-wrap items-center gap-x-3 gap-y-1">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">Ocena ręczna</h3>
        <label className="ml-auto flex items-center gap-1.5 text-xs text-muted">
          Oceniający
          <input
            value={name}
            maxLength={64}
            placeholder="imię / identyfikator"
            onChange={(e) => setName(e.target.value)}
            onBlur={commit}
            onKeyDown={(e) => { if (e.key === "Enter") commit(); }}
            className="h-7 w-40 rounded border border-line bg-surface px-2 text-fg"
          />
        </label>
      </div>
      <p className="mb-2 text-xs text-muted" aria-live="polite">
        {p.submitted
          ? <>Zatwierdzono {fmtDateTime(p.submitted.createdAt)}{comparable > 0 && <> · zgodność z modelem: <b className="text-fg">{agree}/{comparable}</b></>}</>
          : p.blind ? "Tryb ślepy: odpowiedzi modelu pojawią się po zatwierdzeniu oceny." : "Oceń każdy czynnik i zatwierdź."}
      </p>
      <ul className="divide-y divide-line/60 rounded border border-line">
        {p.factors.map((f) => {
          const mine = p.draft[f.id];
          const differs = p.revealed && mine !== undefined && mine !== f.model.answer;
          return (
            <li key={f.id} className={cn("grid grid-cols-[2.25rem_1fr] gap-x-2 gap-y-1.5 px-2 py-2", differs && "bg-risk-mid/10")}>
              <span className="font-mono text-xs text-muted">{p.factors.length > 1 ? f.id : ""}</span>
              <div className="min-w-0">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="font-medium">{f.name}</div>
                    {f.sub && <div className="text-xs text-muted">{f.sub}</div>}
                  </div>
                  <ModelCell f={f} revealed={p.revealed} />
                </div>
                <div className="mt-1.5"><AnswerButtons f={f} value={mine} onPick={(v) => p.onAnswer(f.id, v)} /></div>
              </div>
            </li>
          );
        })}
      </ul>
      <div className="mt-2 flex items-center gap-3">
        <Button variant="primary" disabled={!complete || !name.trim() || p.saving} onClick={() => { commit(); p.onSubmit(name.trim()); }}>
          {p.saving ? "Zapisywanie…" : p.submitted ? "Zatwierdź ponownie" : "Zatwierdź ocenę"}
        </Button>
        <span className="text-xs text-muted">{answered}/{p.factors.length} ocenionych{!name.trim() && " · podaj oceniającego"}</span>
      </div>
      {p.error && <p role="alert" className="mt-1 text-xs text-risk-high">{p.error}</p>}
    </section>
  );
}
