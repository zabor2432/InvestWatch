import type { Evidence } from "../domain/types";

const percentFormatter = new Intl.NumberFormat("pl-PL", {
  style: "percent",
  maximumFractionDigits: 0,
});
const scoreFormatter = new Intl.NumberFormat("pl-PL", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});
const dateTimeFormatter = new Intl.DateTimeFormat("pl-PL", {
  dateStyle: "short",
  timeStyle: "short",
});
const relativeTimeFormatter = new Intl.RelativeTimeFormat("pl-PL", {
  numeric: "auto",
});

export function fmtPct(value: number | null): string {
  return value === null || !Number.isFinite(value) ? "—" : percentFormatter.format(value);
}

export function fmtScore(value: number): string {
  return Number.isFinite(value) ? scoreFormatter.format(value) : "—";
}

export function fmtDateTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : dateTimeFormatter.format(date);
}

export function fmtAgo(value: string): string {
  const timestamp = new Date(value).getTime();
  if (Number.isNaN(timestamp)) return "—";

  const seconds = (timestamp - Date.now()) / 1000;
  const absoluteSeconds = Math.abs(seconds);
  if (absoluteSeconds < 60) return relativeTimeFormatter.format(Math.round(seconds), "second");
  if (absoluteSeconds < 3600) return relativeTimeFormatter.format(Math.round(seconds / 60), "minute");
  if (absoluteSeconds < 86400) return relativeTimeFormatter.format(Math.round(seconds / 3600), "hour");
  if (absoluteSeconds < 30 * 86400) return relativeTimeFormatter.format(Math.round(seconds / 86400), "day");
  if (absoluteSeconds < 365 * 86400) return relativeTimeFormatter.format(Math.round(seconds / (30 * 86400)), "month");
  return relativeTimeFormatter.format(Math.round(seconds / (365 * 86400)), "year");
}

export function isImagePreview(evidence: Evidence): boolean {
  return evidence.kind === "screenshot" || evidence.kind === "snapshot";
}
