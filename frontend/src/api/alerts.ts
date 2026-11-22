import type { AlertEvent } from "../domain/types";
import { debug } from "../lib/log";
import { config } from "./config";
import type { AlertMessageDto } from "./dto";
import { toAlert } from "./mappers";

export type ConnectionState = "connecting" | "open" | "closed";

export interface AlertsChannel {
  /** Zwraca funkcję zamykającą kanał. */
  connect(handlers: { onAlert: (e: AlertEvent) => void; onState: (s: ConnectionState) => void }): () => void;
}

function defaultWsUrl(): string {
  if (config.wsUrl) return config.wsUrl;
  const proto = location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${location.host}/ws/alerts`;
}

/** Prawdziwy WebSocket z auto-reconnectem (backoff do 15 s). */
export const websocketChannel: AlertsChannel = {
  connect({ onAlert, onState }) {
    let ws: WebSocket | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let attempt = 0;
    let stopped = false;

    const open = () => {
      onState("connecting");
      ws = new WebSocket(defaultWsUrl());
      ws.onopen = () => { attempt = 0; onState("open"); };
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(String(ev.data)) as AlertMessageDto;
          if (msg.type === "alert") onAlert(toAlert(msg));
        } catch (err) {
          debug("nieprawidłowa wiadomość WS", err);
        }
      };
      ws.onclose = () => {
        onState("closed");
        if (stopped) return;
        timer = setTimeout(open, Math.min(15000, 1000 * 2 ** attempt++));
      };
      ws.onerror = () => ws?.close();
    };
    open();
    return () => { stopped = true; clearTimeout(timer); ws?.close(); };
  },
};
