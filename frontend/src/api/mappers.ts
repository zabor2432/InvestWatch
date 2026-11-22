import type { AlertEvent, Annotation, IncidentRecord, Report } from "../domain/types";
import { platformSource } from "../domain/labels";
import type { AlertMessageDto, AnnotationDto, RecordDto, RecordsResponseDto, ReportDto } from "./dto";

/**
 * JEDYNE miejsce, które zna pola backendu. Komponenty i hooki używają wyłącznie
 * modelu domenowego z `domain/types`.
 */
export function toRecord(dto: RecordDto): IncidentRecord {
  return {
    id: dto.id,
    module: dto.module,
    detectedAt: dto.detected_at,
    source: platformSource(dto.source),
    publishedAt: dto.published_at ?? undefined,
    url: dto.url,
    title: dto.title,
    content: dto.content,
    score: dto.risk_score,
    status: dto.status,
    entity: { name: dto.entity.name, kind: dto.entity.kind, url: dto.entity.url ?? undefined },
    advertisedFirm: dto.advertised_firm ?? undefined,
    matchedPhrases: dto.matched_phrases ?? undefined,
    rules: dto.rule_results?.map((r) => ({ ruleId: r.rule_id, verdict: r.verdict, score: r.score, note: r.note ?? undefined })),
    evidence: dto.evidence ?? [],
    observationId: dto.observation_id ?? undefined,
    images: dto.images ?? [],
    manipulated: dto.manipulated ?? false,
    manipulatedRules: dto.manipulated_rules?.length ? dto.manipulated_rules : undefined,
    groundTruth: dto.ground_truth ?? undefined,
  };
}

export const toRecords = (res: RecordsResponseDto): IncidentRecord[] => res.items.map(toRecord);

export const toAlert = (msg: AlertMessageDto): AlertEvent => ({ id: msg.id, at: msg.at, record: toRecord(msg.record) });

export function toRecordDto(r: IncidentRecord): RecordDto {
  return {
    id: r.id,
    module: r.module,
    detected_at: r.detectedAt,
    source: r.source,
    url: r.url,
    title: r.title,
    content: r.content,
    risk_score: r.score,
    status: r.status,
    entity: { name: r.entity.name, kind: r.entity.kind, url: r.entity.url },
    advertised_firm: r.advertisedFirm,
    matched_phrases: r.matchedPhrases,
    rule_results: r.rules?.map((x) => ({ rule_id: x.ruleId, verdict: x.verdict, score: x.score, note: x.note })),
    evidence: r.evidence,
    ground_truth: r.groundTruth,
    published_at: r.publishedAt,
    observation_id: r.observationId,
    images: r.images,
    manipulated: r.manipulated,
    manipulated_rules: r.manipulatedRules,
  };
}

export const toAnnotation = (dto: AnnotationDto): Annotation => ({ id: dto.id, annotator: dto.annotator, answers: dto.answers, createdAt: dto.created_at });

export const toReport = (dto: ReportDto): Report => ({
  model: dto.model,
  models: dto.models,
  annotators: dto.annotators,
  judgments: dto.judgments.map((j) => ({ recordId: j.record_id, module: j.module, annotator: j.annotator, factor: j.factor, human: j.human, score: j.score })),
});
