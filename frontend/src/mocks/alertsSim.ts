import type { AlertsChannel } from "../api/alerts";
import type { AlertMessageDto } from "../api/dto";
import { toAlert } from "../api/mappers";
import { makeRecord, rng } from "./generator";
import { store } from "./store";

const r = rng(Date.now() & 0xffff);

/** Symulowany WebSocket: co 12-25 s „wykrywa” rekord wysokiego ryzyka. */
export const simulatedChannel: AlertsChannel = {
  connect({ onAlert, onState }) {
    let timer: ReturnType<typeof setTimeout>;
    let stopped = false;
    onState("connecting");
    const open = setTimeout(() => onState("open"), 400);

    const tick = () => {
      if (stopped) return;
      const rec = makeRecord(r, ++store.counter, { now: Date.now(), forceHigh: true });
      rec.detected_at = new Date().toISOString();
      store.records.unshift(rec);
      const msg: AlertMessageDto = { type: "alert", id: `alert-${rec.id}`, at: rec.detected_at, record: rec };
      onAlert(toAlert(msg));
      timer = setTimeout(tick, 12000 + r() * 13000);
    };
    timer = setTimeout(tick, 6000);
    return () => { stopped = true; clearTimeout(timer); clearTimeout(open); onState("closed"); };
  },
};
