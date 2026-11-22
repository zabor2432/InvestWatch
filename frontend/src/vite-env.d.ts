/// <reference types="vite/client" />
interface ImportMetaEnv {
  readonly VITE_USE_MOCKS?: string;
  readonly VITE_API_URL?: string;
  readonly VITE_WS_URL?: string;
  readonly VITE_DEBUG?: string;
  /** Wersja statyczna demo (mocki + wygenerowane oceny analityków), tylko w `npm run build:demo` */
  readonly VITE_DEMO?: string;
}
