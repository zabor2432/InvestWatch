import type { Annotation, Answer, IncidentRecord, RecordStatus, Report } from "../domain/types";
import { config } from "./config";
import type { AnnotationDto, AnnotationInDto, RecordDto, RecordsResponseDto, RefreshRunDto, ReportDto, StatusUpdateDto } from "./dto";
import { toAnnotation, toRecord, toRecords, toReport } from "./mappers";

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${config.apiUrl}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status} ${path}`);
  return (await res.json()) as T;
}

export interface RefreshRun {
  runId: string;
  status: string;
  alreadyRunning: boolean;
}

const toRun = (d: RefreshRunDto): RefreshRun => ({ runId: d.run_id, status: d.status, alreadyRunning: d.already_running });

export const api = {
  /** "Odśwież dane": start przetwarzania w Dagsterze (trwający run jest zwracany zamiast drugiego). */
  async startRefresh(): Promise<RefreshRun> {
    return toRun(await http<RefreshRunDto>("/refresh", { method: "POST" }));
  },
  async refreshStatus(runId: string): Promise<RefreshRun> {
    return toRun(await http<RefreshRunDto>(`/refresh/${encodeURIComponent(runId)}`));
  },
  async listRecords(): Promise<IncidentRecord[]> {
    return toRecords(await http<RecordsResponseDto>("/records"));
  },
  async updateStatus(id: string, status: RecordStatus): Promise<IncidentRecord> {
    const body: StatusUpdateDto = { status };
    const dto = await http<RecordDto>(`/records/${encodeURIComponent(id)}/status`, { method: "PATCH", body: JSON.stringify(body) });
    return toRecord(dto);
  },
  /** Ostatnie oceny danego oceniającego (najnowsza pierwsza). */
  async listAnnotations(id: string, annotator: string): Promise<Annotation[]> {
    const dtos = await http<AnnotationDto[]>(`/records/${encodeURIComponent(id)}/annotations?annotator=${encodeURIComponent(annotator)}`);
    return dtos.map(toAnnotation);
  },
  /** Raport odchyleń: oceny ręczne vs wybrany model (bez `model` = model z największą liczbą wyników). */
  async report(model?: string): Promise<Report> {
    return toReport(await http<ReportDto>(`/report${model ? `?model=${encodeURIComponent(model)}` : ""}`));
  },
  /** Zatwierdzenie oceny: zawsze nowy wpis (wielu oceniających, wielokrotne zatwierdzenia). */
  async submitAnnotation(id: string, annotator: string, answers: Record<string, Answer>): Promise<Annotation> {
    const body: AnnotationInDto = { annotator, answers };
    return toAnnotation(await http<AnnotationDto>(`/records/${encodeURIComponent(id)}/annotations`, { method: "POST", body: JSON.stringify(body) }));
  },
};
