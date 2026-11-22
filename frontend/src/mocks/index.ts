import { setupWorker } from "msw/browser";
import { handlers } from "./handlers";

export { simulatedChannel } from "./alertsSim";

export async function startMocks() {
  await setupWorker(...handlers).start({ quiet: true, serviceWorker: { url: `${import.meta.env.BASE_URL}mockServiceWorker.js` } }); // względnie: strona może leżeć w podkatalogu
}
