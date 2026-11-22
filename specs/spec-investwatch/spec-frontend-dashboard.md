---
title: 'Frontend InvestWatch: dashboard analityczny (MVP na mockach)'
type: 'feature'
created: '2026-11-21'
status: 'done'
baseline_commit: '7447e66344abee45f04083c432ce2fa8a833c2fe'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Frontend to goły scaffold (`<h1>`). Jury UKNF oceni dashboard (PDF, sekcja 3.3 i 6), ale backend i modele AI jeszcze nie istnieją.

**Approach:** Desktop-first dashboard po polsku (React 18 + TS + Tailwind + shadcn/Radix + TanStack Table), zasilany mockami MSW i symulowanym WebSocketem przez warstwę adaptera DTO→model domenowy, z przełączaniem mock/real w `.env`.

## Boundaries & Constraints

**Always:**
- Komponenty prezentacyjne sterowane propsami; logika danych w hookach.
- Jeden plik mappera DTO→model; komponenty nie znają kształtu body backendu.
- Konsola przeglądarki czysta (0 błędów/ostrzeżeń); logi tylko pod `VITE_DEBUG`.
- Ryzyko oznaczone etykietą tekstową, nie samym kolorem. Fonty self-hosted.
- Dockerfile: `npm ci` z lockfile. `npm audit` bez krytycznych.
- Próg globalny; surowy score w danych, filtrowanie progiem po stronie klienta.
- Statusy: `nowy → w analizie → potwierdzony | fałszywy alarm`.

**Ask First:** zmiany poza `frontend/` (poza dopisaniem `VITE_*` do `.env.example`).

**Never:** płatne API/CDN, importy z innych serwisów, wykresy trendów i KPI (idą do `frontend/TODO.md`), zmiany w README ponad minimum.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Filtrowanie | data, źródło, ryzyko, moduł 1/2/3 | lista zawęża się, filtry w URL | brak wyników → pusty stan |
| Zmiana statusu | wybór statusu w szczegółach | optymistyczna aktualizacja listy i szczegółów | błąd API → rollback + toast |
| Alert WS | zdarzenie wysokiego ryzyka | toast + wpis w centrum powiadomień + licznik | rozłączenie → wskaźnik i auto-reconnect |
| Zmiana progu | suwak threshold | lista i liczby TP/FP/FN/precision/recall przeliczone na żywo | próg poza 0–1 → clamp |
| Rekord modułu 2 | 18 reguł (1–11, 12a, 12b, 13–18) | karta: status, podstawa prawna, wynik | reguła bez wyniku → „nie dotyczy" |

</frozen-after-approval>

## Code Map

- `frontend/` -- Vite+React scaffold, `package.json`, `Dockerfile`, `src/App.jsx`, `src/main.jsx` do migracji na TS.
- `.env.example` -- dopisać `VITE_USE_MOCKS`, `VITE_API_URL`, `VITE_WS_URL`, `VITE_DEBUG`.
- `UKNF/zasoby/*kryteria oceny informacji o ryzyku.docx` -- źródło 18 reguł i podstaw prawnych.

## Tasks & Acceptance

**Execution:**
- [x] `frontend/package.json`, `tsconfig*.json`, `vite.config.ts`, `tailwind`, lockfile -- TS, Tailwind, Radix, TanStack Table, Recharts, MSW, Vitest -- stos
- [x] `frontend/Dockerfile` -- `npm ci`, serwowanie nginx z fallbackiem SPA -- wymóg pkt 5
- [x] `frontend/src/domain/` -- typy modelu, 18 reguł (id, nazwa, opis, podstawa prawna) -- sedno modułu 2
- [x] `frontend/src/api/` -- klient REST, kliencki WS, `mappers.ts` (DTO→domena), przełącznik mock/real -- łatwa adaptacja
- [x] `frontend/src/mocks/` -- MSW handlers, generator rekordów (3 moduły), symulator WS -- dane do demo
- [x] `frontend/src/hooks/` -- rekordy, filtry w URL, status, threshold, powiadomienia, skróty klawiszowe -- logika
- [x] `frontend/src/components/` + `src/pages/` -- layout, tabela, filtry, panel szczegółów, karta reguł, centrum powiadomień, kalibracja, motyw -- UI PL
- [x] `frontend/src/**/*.test.*` -- testy mappera, przeliczania progu, filtrów -- wiersze I/O
- [x] `frontend/TODO.md`, `frontend/THIRD_PARTY.md` -- wykresy/KPI; biblioteki z licencjami

**Acceptance Criteria:**
- Given `VITE_USE_MOCKS=true`, when otwieram dashboard, then widzę listę rekordów z 3 modułów i konsola jest czysta.
- Given rekord modułu 2, when otwieram szczegóły, then widzę 18 reguł ze statusem, podstawą prawną i wynikiem.
- Given tabela, when naciskam `j/k` i `/`, then zaznaczenie się przesuwa i fokus trafia do filtra.
- Given zmianę progu, when przesuwam suwak, then liczby FP/FN i precision/recall zmieniają się natychmiast.
- Given `docker build ./frontend`, then build przechodzi, a `npm audit` nie raportuje krytycznych.

## Design Notes

Adapter: `api/client.ts` zwraca DTO, `api/mappers.ts` jedyne miejsce znające pola backendu. Zmiana schematu = edycja mappera + typów DTO.

## Verification

**Commands:**
- `cd frontend && npm run build && npm test` -- expected: sukces
- `cd frontend && npm audit --audit-level=critical` -- expected: 0 krytycznych

**Manual checks:**
- `npm run dev`, przeglądarka: konsola bez wpisów, alert WS pojawia się po kilkunastu sekundach.

## Suggested Review Order

**Adapter API (punkt wejścia)**

- Jedyne miejsce znające pola backendu; zmiana schematu = edycja tego pliku.
  [`mappers.ts:8`](../../frontend/src/api/mappers.ts#L8)

- Kształt body backendu (DTO).
  [`dto.ts:1`](../../frontend/src/api/dto.ts#L1)

- Wybór mock/real dla WebSocketu, reconnect z backoffem.
  [`index.ts:9`](../../frontend/src/api/index.ts#L9)

**Mocki**

- Deterministyczny generator rekordów dla 3 modułów i reguł 1–18.
  [`generator.ts:1`](../../frontend/src/mocks/generator.ts#L1)

- Symulator alertów wysokiego ryzyka.
  [`alertsSim.ts:9`](../../frontend/src/mocks/alertsSim.ts#L9)

**Logika domenowa**

- Macierz pomyłek, precision/recall dla progu.
  [`risk.ts:25`](../../frontend/src/domain/risk.ts#L25)

- Reguły 1–18 z podstawą prawną.
  [`rules.ts:9`](../../frontend/src/domain/rules.ts#L9)

**Kompozycja i UI**

- Składanie hooków, skróty klawiszowe, przepływ alertów.
  [`App.tsx:21`](../../frontend/src/App.tsx#L21)

- Tabela: sortowanie, sticky nagłówek.
  [`RecordsTable.tsx:35`](../../frontend/src/components/RecordsTable.tsx#L35)

- Karta reguł modułu 2.
  [`RulesCard.tsx:17`](../../frontend/src/components/RulesCard.tsx#L17)

- Panel kalibracji.
  [`CalibrationPanel.tsx:50`](../../frontend/src/components/CalibrationPanel.tsx#L50)

**Peryferia**

- Testy, Dockerfile, nginx, TODO, licencje.
  [`risk.test.ts:1`](../../frontend/src/domain/risk.test.ts#L1)
  [`Dockerfile:1`](../../frontend/Dockerfile#L1)
