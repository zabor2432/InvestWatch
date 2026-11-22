import { useCallback, useState } from "react";

export interface Toast {
  id: string;
  title: string;
  description?: string;
  tone: "info" | "danger" | "success";
  recordId?: string;
}

export function useToasts(ttlMs = 8000) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const dismiss = useCallback((id: string) => setToasts((t) => t.filter((x) => x.id !== id)), []);
  const push = useCallback((t: Omit<Toast, "id">) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
    setToasts((prev) => [...prev, { ...t, id }].slice(-4));
    setTimeout(() => dismiss(id), ttlMs);
  }, [dismiss, ttlMs]);
  return { toasts, push, dismiss };
}
