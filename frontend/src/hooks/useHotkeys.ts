import { useEffect, useRef } from "react";

type Handlers = Record<string, (e: KeyboardEvent) => void>;

const isTyping = (t: EventTarget | null) => {
  const el = t as HTMLElement | null;
  return !!el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable);
};

/** Globalne skróty jednoklawiszowe; ignorowane podczas pisania w polach. Esc działa zawsze. */
export function useHotkeys(handlers: Handlers) {
  const ref = useRef(handlers);
  ref.current = handlers;
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      if (isTyping(e.target) && e.key !== "Escape") return;
      const fn = ref.current[e.key];
      if (fn) fn(e);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
}
