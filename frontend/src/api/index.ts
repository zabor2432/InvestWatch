import type { AlertsChannel } from "./alerts";
import { websocketChannel } from "./alerts";
import { config } from "./config";

export { api, type RefreshRun } from "./client";
export type { AlertsChannel, ConnectionState } from "./alerts";

/** Wybór kanału alertów: symulator (mock) lub prawdziwy WebSocket. */
export async function getAlertsChannel(): Promise<AlertsChannel> {
  if (config.useMocks) return (await import("../mocks")).simulatedChannel;
  return websocketChannel;
}
