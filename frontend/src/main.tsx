import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { config } from "./api/config";
import "./index.css";

async function bootstrap() {
  if (config.useMocks) await (await import("./mocks")).startMocks();
  // Bez mocków: wyrejestruj service worker MSW zostawiony przez wcześniejsze wizyty (inaczej podaje fałszywe dane).
  else if ("serviceWorker" in navigator) {
    for (const reg of await navigator.serviceWorker.getRegistrations()) await reg.unregister();
  }
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}
void bootstrap();
