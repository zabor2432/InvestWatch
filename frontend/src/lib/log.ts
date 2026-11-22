export function debug(topic: string, ...details: unknown[]): void {
  if (import.meta.env.VITE_DEBUG === "true") {
    console.debug(`[${topic}]`, ...details);
  }
}
