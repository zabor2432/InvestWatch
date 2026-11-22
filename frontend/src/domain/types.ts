export type ModuleId = 1 | 2 | 3;
export type RiskLevel = "low" | "medium" | "high";
export type RecordStatus = "new" | "in_review" | "confirmed" | "false_positive";
export type Source = "Facebook" | "Instagram" | "TikTok" | "YouTube" | "Telegram" | "TradingView" | "WWW";

export type EntityKind = "investment_firm" | "finfluencer" | "unauthorized";

export interface Entity {
  name: string;
  kind: EntityKind;
  url?: string;
}

export interface Evidence {
  kind: "screenshot" | "snapshot" | "phrase" | "hash";
  label: string;
  value: string;
}

export type RuleVerdict = "pass" | "fail" | "uncertain" | "n/a";

export interface RuleResult {
  ruleId: string;
  verdict: RuleVerdict;
  /** 0..1, pewność modelu co do naruszenia reguły */
  score: number;
  note?: string;
}

export type ImageVariant = "desktop" | "mobile" | "tablet" | "original";

/** Obraz materiału: wariant ekranu i ostrość (cała strona albo wycięty blok z informacją o ryzyku). */
export interface RecordImage {
  variant: ImageVariant;
  focus: "page" | "risk";
  url: string;
}

export interface IncidentRecord {
  id: string;
  module: ModuleId;
  detectedAt: string; // ISO, kiedy zebrano
  publishedAt?: string; // ISO, kiedy opublikowano u źródła
  source: Source;
  url: string;
  title: string;
  content: string;
  /** Surowy score modelu 0..1 - próg stosowany po stronie klienta */
  score: number;
  status: RecordStatus;
  entity: Entity;
  /** Moduł 1: reklamowana firma inwestycyjna */
  advertisedFirm?: string;
  /** Moduł 3: wykryte frazy */
  matchedPhrases?: string[];
  /** Moduł 2: wyniki reguł 1-18 */
  rules?: RuleResult[];
  evidence: Evidence[];
  /** Ta sama para (podmiot, firma): rekordy o tym id tworzą historię obserwacji */
  observationId?: string;
  images: RecordImage[];
  /** Kontrolowany wariant testowy (celowo zepsuty), nie prawdziwy materiał */
  manipulated: boolean;
  /** Reguły, które wariant testowy miał celowo złamać */
  manipulatedRules?: string[];
  /** Etykieta referencyjna (jeśli znana) - do liczenia FP/FN w kalibracji */
  groundTruth?: boolean;
}

export interface Filters {
  q: string;
  modules: ModuleId[];
  sources: Source[];
  levels: RiskLevel[];
  statuses: RecordStatus[];
  from: string; // YYYY-MM-DD lub ""
  to: string;
}

export interface AlertEvent {
  id: string;
  at: string;
  record: IncidentRecord;
}

/** Odpowiedź oceniającego: 1 = oflagowane (naruszenie / reklama / doradztwo), 0 = zgodne, null = nie dotyczy */
export type Answer = 0 | 1 | null;

export interface Annotation {
  id: number;
  annotator: string;
  answers: Record<string, Answer>;
  createdAt: string;
}

/** Ocena człowieka dla czynnika zestawiona z odpowiedzią modelu (score null = model: nie dotyczy). */
export interface Judgment {
  recordId: string;
  module: ModuleId;
  annotator: string;
  factor: string;
  human: Answer;
  score: number | null;
}

export interface Report {
  model: string | null;
  models: { model: string; results: number }[];
  annotators: string[];
  judgments: Judgment[];
}
