import { useCallback, useEffect, useRef, useState } from "react";
import { getAlertsChannel, type ConnectionState } from "../api";
import type { AlertEvent } from "../domain/types";

export interface Notification extends AlertEvent {
  read: boolean;
}

export function useAlerts(onAlert: (e: AlertEvent) => void) {
  const [connection, setConnection] = useState<ConnectionState>("connecting");
  const [items, setItems] = useState<Notification[]>([]);
  const handler = useRef(onAlert);
  handler.current = onAlert;

  useEffect(() => {
    let close: (() => void) | undefined;
    let cancelled = false;
    getAlertsChannel().then((channel) => {
      if (cancelled) return;
      close = channel.connect({
        onState: setConnection,
        onAlert: (e) => {
          setItems((prev) => [{ ...e, read: false }, ...prev].slice(0, 50));
          handler.current(e);
        },
      });
    });
    return () => { cancelled = true; close?.(); };
  }, []);

  const markAllRead = useCallback(() => setItems((p) => p.map((n) => ({ ...n, read: true }))), []);
  const unread = items.filter((n) => !n.read).length;
  return { connection, notifications: items, unread, markAllRead };
}
