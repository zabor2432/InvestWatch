import type { EntityKind, ImageVariant, ModuleId, RecordStatus, RiskLevel, Source } from "./types";

export const MODULE_LABEL: Record<ModuleId, string> = {
  1: "M1 Finfluencerzy",
  2: "M2 Informacja o ryzyku",
  3: "M3 Shadow Advisory",
};
export const MODULES: ModuleId[] = [1, 2, 3];

export const LEVEL_LABEL: Record<RiskLevel, string> = {
  low: "Niskie",
  medium: "Średnie",
  high: "Wysokie",
};
export const LEVELS: RiskLevel[] = ["high", "medium", "low"];

export const STATUS_LABEL: Record<RecordStatus, string> = {
  new: "Nowy",
  in_review: "W analizie",
  confirmed: "Potwierdzony",
  false_positive: "Fałszywy alarm",
};
export const STATUSES: RecordStatus[] = ["new", "in_review", "confirmed", "false_positive"];

export const SOURCES: Source[] = ["Facebook", "Instagram", "TikTok", "YouTube", "Telegram", "TradingView", "WWW"];

/** Platforma z backendu (np. "youtube") -> etykieta źródła; nieznane trafiają do WWW. */
export const platformSource = (platform: string): Source => SOURCES.find((s) => s.toLowerCase() === platform.toLowerCase()) ?? "WWW";

export const VARIANT_LABEL: Record<ImageVariant, string> = { desktop: "Komputer", mobile: "Telefon", tablet: "Tablet", original: "Oryginał" };

export const ENTITY_LABEL: Record<EntityKind, string> = {
  investment_firm: "Firma inwestycyjna",
  finfluencer: "Finfluencer / podmiot trzeci",
  unauthorized: "Podmiot nieautoryzowany",
};
