import * as Popover from "@radix-ui/react-popover";
import { Bell } from "lucide-react";
import type { Notification } from "../hooks/useAlerts";
import { fmtAgo } from "../lib/format";
import { MODULE_LABEL } from "../domain/labels";
import { RiskBadge } from "./RiskBadge";

interface Props {
  items: Notification[];
  unread: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onOpenRecord: (id: string) => void;
}

export function NotificationCenter({ items, unread, open, onOpenChange, onOpenRecord }: Props) {
  return (
    <Popover.Root open={open} onOpenChange={onOpenChange}>
      <Popover.Trigger className="relative inline-flex h-8 w-8 items-center justify-center rounded border border-line bg-surface hover:bg-raised" aria-label={`Powiadomienia (n), nieprzeczytane: ${unread}`} title="Powiadomienia (n)">
        <Bell className="h-4 w-4" aria-hidden />
        {unread > 0 && <span className="absolute -right-1 -top-1 min-w-4 rounded-full bg-risk-high px-1 text-center text-xs font-semibold leading-4 text-bg">{unread}</span>}
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content align="end" sideOffset={6} className="z-50 w-96 rounded border border-line bg-surface shadow-lg">
          <div className="border-b border-line px-3 py-2 text-sm font-semibold">Powiadomienia o wysokim ryzyku</div>
          <ul className="max-h-96 overflow-y-auto">
            {items.length === 0 && <li className="p-4 text-center text-muted">Brak powiadomień. Nowe pojawią się tu na żywo.</li>}
            {items.map((n) => (
              <li key={n.id} className="border-b border-line/60 last:border-0">
                <button type="button" onClick={() => { onOpenRecord(n.record.id); onOpenChange(false); }} className="flex w-full flex-col gap-1 px-3 py-2 text-left hover:bg-raised">
                  <span className="flex items-center gap-2">
                    {!n.read && <span className="h-2 w-2 rounded-full bg-accent" aria-label="nieprzeczytane" />}
                    <RiskBadge score={n.record.score} />
                    <span className="text-xs text-muted">{MODULE_LABEL[n.record.module].split(" ")[0]} · {fmtAgo(n.at)}</span>
                  </span>
                  <span className="font-medium">{n.record.entity.name}</span>
                  <span className="truncate text-xs text-muted">{n.record.title}</span>
                </button>
              </li>
            ))}
          </ul>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
