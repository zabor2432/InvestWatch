import { delay, http, HttpResponse } from "msw";
import type { AnnotationDto, AnnotationInDto, RecordDto, RecordsResponseDto, ReportDto, StatusUpdateDto } from "../api/dto";
import { seedDemoAnnotations } from "./demoAnnotations";
import { store } from "./store";

const annotations: AnnotationDto[] = [];
const byRecord = new Map<string, AnnotationDto[]>();
if (import.meta.env.VITE_DEMO === "true") annotations.push(...seedDemoAnnotations(store.records, byRecord)); // wersja statyczna: gotowe oceny analityków

let runPolls = 0;

export const handlers = [
  http.post("*/api/refresh", () => {
    runPolls = 0;
    return HttpResponse.json({ run_id: "mock-run-0001", status: "QUEUED", already_running: false }, { status: 202 });
  }),
  http.get("*/api/refresh/:id", ({ params }) =>
    HttpResponse.json({ run_id: params.id, status: ++runPolls < 2 ? "STARTED" : "SUCCESS", already_running: false }),
  ),
  http.get("*/api/records/:id/annotations", ({ params, request }) => {
    const who = new URL(request.url).searchParams.get("annotator");
    return HttpResponse.json((byRecord.get(String(params.id)) ?? []).filter((a) => !who || a.annotator === who));
  }),
  http.get("*/api/report", () => {
    const judgments: ReportDto["judgments"] = [];
    for (const [rid, list] of byRecord) {
      const rec = store.records.find((r) => r.id === rid);
      if (!rec) continue;
      const latest = new Map<string, AnnotationDto>();
      for (const a of list) if (!latest.has(a.annotator)) latest.set(a.annotator, a); // lista: najnowsza pierwsza
      for (const a of latest.values()) {
        for (const [factor, human] of Object.entries(a.answers)) {
          const rule = rec.rule_results?.find((r) => r.rule_id === factor);
          judgments.push({ record_id: rid, module: rec.module, annotator: a.annotator, factor, human, score: rec.module === 2 ? (rule && rule.verdict !== "n/a" ? rule.score : null) : rec.risk_score });
        }
      }
    }
    return HttpResponse.json({ model: "mock", models: [{ model: "mock", results: store.records.length }], annotators: [...new Set(judgments.map((j) => j.annotator))].sort(), judgments } satisfies ReportDto);
  }),
  http.post("*/api/records/:id/annotations", async ({ params, request }) => {
    const body = (await request.json()) as AnnotationInDto;
    const a: AnnotationDto = { id: annotations.length + 1, annotator: body.annotator, answers: body.answers, created_at: new Date().toISOString() };
    annotations.push(a);
    byRecord.set(String(params.id), [a, ...(byRecord.get(String(params.id)) ?? [])]);
    return HttpResponse.json(a, { status: 201 });
  }),
  http.get("*/api/records", async () => {
    await delay(250);
    const body: RecordsResponseDto = { items: store.records, total: store.records.length };
    return HttpResponse.json(body);
  }),
  http.patch("*/api/records/:id/status", async ({ params, request }) => {
    await delay(150);
    const { status } = (await request.json()) as StatusUpdateDto;
    const rec = store.records.find((r) => r.id === params.id);
    if (!rec) return HttpResponse.json({ detail: "Not found" }, { status: 404 });
    rec.status = status;
    return HttpResponse.json(rec satisfies RecordDto);
  }),
];
