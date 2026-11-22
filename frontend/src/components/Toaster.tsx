import { X } from "lucide-react";
import type { Toast } from "../hooks/useToasts";
import { cn } from "./ui/cn";

interface Props {
  toasts: Toast[];
  onDismiss: (id: string) => void;
  onOpenRecord: (id: string) => void;
}

const TONE = { info: "border-line", danger: "border-risk-high", success: "border-risk-low" } as const;

export function Toaster({ toasts, onDismiss, onOpenRecord }: Props) {
  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-80 flex-col gap-2" role="status" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className={cn("pointer-events-auto flex gap-2 rounded border-l-4 border bg-surface p-3 shadow-lg", TONE[t.tone])}>
          <div className="min-w-0 flex-1">
            <div className="font-semibold">{t.title}</div>
            {t.description && <div className="truncate text-xs text-muted">{t.description}</div>}
            {t.recordId && (
              <button type="button" onClick={() => { onOpenRecord(t.recordId!); onDismiss(t.id); }} className="mt-1 text-xs text-accent hover:underline">
                Otwórz rekord
              </button>
            )}
          </div>
          <button type="button" onClick={() => onDismiss(t.id)} aria-label="Zamknij powiadomienie" className="self-start text-muted hover:text-fg">
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>
      ))}
    </div>
  );
}
