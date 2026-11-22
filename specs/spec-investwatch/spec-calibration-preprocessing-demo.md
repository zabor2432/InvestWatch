---
title: 'Progi per reguła, preprocessing w Dagsterze, statyczne demo, dokumentacja'
type: 'feature'
created: '2026-11-22'
status: 'done'
baseline_commit: 'e2079b5'
context: ['specs/spec-investwatch/spec-frontend-dashboard.md', 'UKNF/UKNF - Pełna treść zadania konkursowego.pdf']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** (1) Reguły modułu 2 nie są jednakowe (np. rozmiar tekstu bywa flagowany za często), a próg jest jeden; analitycy mają oceny, z których da się go dobrać, ale ręczne przeklikiwanie jest nierealne na demo. (2) UKNF wymaga preprocessingu tekstu (HTML, normalizacja, duplikaty, tokeny i wektory) przed analizą. (3) Dokumentacja nie pokazuje stanu obecnego i docelowego.

**Approach:** Próg globalny (domyślnie 0.5) plus nadpisania per reguła, liczone przy odczycie; sugestia progu z ocen analityków (maksimum F1). Osobny asset `preprocessed_batch` przed podziałem na moduły. Statyczna kopia dashboardu z wygenerowanymi ocenami jako osobny build, bez zmian w oryginale. Dokumentacja i specyfikacje zgodne z kodem.

## Boundaries & Constraints

**Always:**
- Surowy score w bazie; progi stosowane przy odczycie (nic się nie przelicza po zmianie progu).
- Tylko reguły modułu 2 mają własne progi; moduły 1 i 3 używają globalnego.
- Preprocessing bez nowych zależności (czysty Python); duplikat tekstu dostaje wynik oryginału bez drugiego wywołania modelu.
- Wersja statyczna powstaje flagą buildu (`VITE_DEMO`), oryginalny dashboard i API się nie zmieniają.

**Ask First:** zapis progów po stronie serwera (dziś w przeglądarce), neuralne embeddingi, zewnętrzne usługi logowania.

**Never:** zmiana wyniku w bazie przy zmianie progu; wciskanie wygenerowanych ocen do prawdziwej bazy.

## I/O & Edge-Case Matrix

| Scenariusz | Wejście / stan | Oczekiwane zachowanie | Obsługa błędów |
|---|---|---|---|
| Sugestia progu | ≥5 porównywalnych ocen reguły | próg o najlepszym F1 (siatka 0.05, przy remisie środek) | <5 ocen: "za mało ocen" |
| Analitycy nie widzą naruszeń | same oceny "zgodne" | próg tuż nad najwyższym score zgodnych | brak |
| Rekord M2 | reguła 4 próg 0.7, score 0.65 | reguła nie flaguje; rekord flagowany, gdy inna reguła przekroczy swój próg | "nie dotyczy" nie liczy się |
| Duplikat tekstu | cosinus ≥ 0.95, ten sam moduł, bez obrazów | `duplicate_of`, wynik oryginału | materiały z obrazami zawsze osobno |
| Statyczne demo | podkatalog serwowany przez `http.server` | pełny dashboard z ocenami 3 analityków | service worker względem `BASE_URL` |

</frozen-after-approval>

## Code Map

- `frontend/src/domain/thresholds.ts`, `hooks/useThreshold.ts`, `components/RuleThresholds.tsx` -- progi, sugestia, panel.
- `frontend/src/mocks/demoAnnotations.ts`, `package.json` (`build:demo`) -- wygenerowane oceny i build statyczny → `demo/dashboard-static/`.
- `orchestrator/pipeline/preprocess.py`, `definitions.py` (`preprocessed_batch`) -- tokeny, wektor cech, duplikaty.
- `docs/`, `README.md` -- macierz zgodności z UKNF, architektura obecna i docelowa, miejsca podglądu.

## Tasks & Acceptance

- [x] Progi per reguła + sugestia + panel w Kalibracji; raport i szczegóły liczą wg progów reguł
- [x] `preprocessed_batch` i testy
- [x] Statyczne demo z wygenerowanymi ocenami
- [x] Macierz zgodności, architektura (obecna i docelowa), README, specyfikacje

**Acceptance Criteria:**
- Given oceny analityków, when otwieram Kalibrację, then widzę per regułę zgodność dziś, próg, sugestię i zgodność przy sugestii; "Zastosuj sugestie" ustawia progi.
- Given próg reguły 4 podniesiony, when wracam do listy i raportu, then lista, szczegóły i raport używają tego progu.
- Given dwa takie same wpisy w batchu, when run się kończy, then model był wołany raz, a oba dokumenty mają wynik.
- Given `cd demo/dashboard-static && python3 -m http.server`, then dashboard działa offline z gotowymi ocenami.

## Verification

- `cd frontend && npm run typecheck && npm test && npm run build:demo`; `cd orchestrator && uv run pytest -q`
- Headless Chromium na statycznym buildzie (raport, kalibracja, sugestie).
- Niezweryfikowane: progi per reguła na ocenach prawdziwych analityków (dane demo są wygenerowane).
