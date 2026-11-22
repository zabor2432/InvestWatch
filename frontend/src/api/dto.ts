/**
 * Kształt body zwracanego przez backend (FastAPI). To jedyny plik opisujący
 * format przewodowy. Gdy backend zmieni schemat: popraw te typy i `mappers.ts`.
 */
export interface EntityDto {
  name: string;
  kind: "investment_firm" | "finfluencer" | "unauthorized";
  url?: string | null;
}

export interface EvidenceDto {
  kind: "screenshot" | "snapshot" | "phrase" | "hash";
  label: string;
  value: string;
}

export interface RuleResultDto {
  rule_id: string;
  verdict: "pass" | "fail" | "uncertain" | "n/a";
  score: number;
  note?: string | null;
}

export interface RecordImageDto {
  variant: "desktop" | "mobile" | "tablet" | "original";
  focus: "page" | "risk";
  url: string;
}

export interface RefreshRunDto {
  run_id: string;
  status: string;
  already_running: boolean;
}

export interface RecordDto {
  id: string;
  module: 1 | 2 | 3;
  detected_at: string;
  source: string;
  url: string;
  title: string;
  content: string;
  risk_score: number;
  status: "new" | "in_review" | "confirmed" | "false_positive";
  entity: EntityDto;
  advertised_firm?: string | null;
  matched_phrases?: string[] | null;
  rule_results?: RuleResultDto[] | null;
  evidence?: EvidenceDto[] | null;
  ground_truth?: boolean | null;
  published_at?: string | null;
  observation_id?: string | null;
  images?: RecordImageDto[] | null;
  manipulated?: boolean | null;
  manipulated_rules?: string[] | null;
}

export interface RecordsResponseDto {
  items: RecordDto[];
  total: number;
}

export interface StatusUpdateDto {
  status: RecordDto["status"];
}

/** Wiadomość z WebSocketu /ws/alerts */
export interface AlertMessageDto {
  type: "alert";
  id: string;
  at: string;
  record: RecordDto;
}

export interface AnnotationDto {
  id: number;
  annotator: string;
  answers: Record<string, 0 | 1 | null>;
  created_at: string;
}

export interface AnnotationInDto {
  annotator: string;
  answers: Record<string, 0 | 1 | null>;
}

export interface ReportDto {
  model: string | null;
  models: { model: string; results: number }[];
  annotators: string[];
  judgments: { record_id: string; module: 1 | 2 | 3; annotator: string; factor: string; human: 0 | 1 | null; score: number | null }[];
}
