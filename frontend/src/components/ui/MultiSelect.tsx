import * as Popover from "@radix-ui/react-popover";
import { Check, ChevronDown } from "lucide-react";
import { cn } from "./cn";

interface Props<T extends string | number> {
  label: string;
  options: readonly T[];
  selected: T[];
  getLabel: (v: T) => string;
  onChange: (next: T[]) => void;
}

export function MultiSelect<T extends string | number>({ label, options, selected, getLabel, onChange }: Props<T>) {
  const toggle = (v: T) => onChange(selected.includes(v) ? selected.filter((x) => x !== v) : [...selected, v]);
  return (
    <Popover.Root>
      <Popover.Trigger
        className={cn(
          "inline-flex h-8 items-center gap-1.5 rounded border px-2.5 text-sm hover:bg-raised",
          selected.length ? "border-accent bg-accent/10" : "border-line bg-surface",
        )}
      >
        {label}
        {selected.length > 0 && <span className="rounded bg-accent px-1 text-xs font-medium text-bg">{selected.length}</span>}
        <ChevronDown className="h-3.5 w-3.5 text-muted" aria-hidden />
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content align="start" sideOffset={4} className="z-50 min-w-48 rounded border border-line bg-surface p-1 shadow-lg">
          {options.map((o) => {
            const on = selected.includes(o);
            return (
              <button
                key={o}
                type="button"
                role="menuitemcheckbox"
                aria-checked={on}
                onClick={() => toggle(o)}
                className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm hover:bg-raised"
              >
                <span className={cn("flex h-4 w-4 items-center justify-center rounded border", on ? "border-accent bg-accent text-bg" : "border-line")}>
                  {on && <Check className="h-3 w-3" aria-hidden />}
                </span>
                {getLabel(o)}
              </button>
            );
          })}
          {selected.length > 0 && (
            <button type="button" onClick={() => onChange([])} className="mt-1 w-full border-t border-line px-2 pt-1.5 text-left text-xs text-muted hover:text-fg">
              Wyczyść
            </button>
          )}
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
