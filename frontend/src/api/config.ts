const env = import.meta.env;

export const config = {
  useMocks: env.VITE_USE_MOCKS === "true",
  apiUrl: (env.VITE_API_URL ?? "/api").replace(/\/$/, ""),
  wsUrl: env.VITE_WS_URL ?? "",
};
