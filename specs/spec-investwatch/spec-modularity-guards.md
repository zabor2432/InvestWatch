---
title: 'Modularność: strażnicy spójności między projektami, lint scrapera, stabilne demo'
type: 'chore'
created: '2026-11-22'
status: 'done'
baseline_commit: 'a73d1d7'
context: ['AGENTS.md', 'docs/architecture.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Usługi nie importują się nawzajem (łączy je kontrakt przez dane), więc wiedza powtórzona w kilku projektach (nazwy modułów, tabele, id reguł) może się rozjechać bez żadnego błędu. Kod scrapera nie miał testów ani lintu, zbudowane demo (`demo/dashboard-static`) generowało szum w diffach, a lokalne bramki były rozproszone.

**Approach:** Nie wiązać projektów kodem, tylko pilnować spójności testem i CI. Minimalne zmiany w cudzym kodzie (bez reformatowania), testy czystej logiki scrapera, stabilne nazwy plików demo i kontrola jego aktualności w CI.

## Boundaries & Constraints

**Always:**
- Projekty pozostają niezależne (bez importów między usługami); zgodność sprawdza `orchestrator/tests/test_consistency.py`.
- Zmiany w `scraper/` ograniczone do zgodności z lintem (bez zmian zachowania) i testów; bez reformatowania plików współpracownika.
- Wszystkie lokalne bramki jednym poleceniem: `scripts/check.sh`.

**Never:** zmiana promptów modelu bez pomiaru jakości (nazwy reguł w `rules.py` i w UI mogą się różnić), wspólny kod między usługami poza `common/`.

## I/O & Edge-Case Matrix

| Scenariusz | Wejście / stan | Oczekiwane zachowanie |
|---|---|---|
| Nowy moduł albo zmiana nazwy w jednym projekcie | `contract.MODULES` vs baza, backend, adapter, seed, collect | test spójności pada i wskazuje plik |
| Nowa tabela scrapera o nazwie naszej tabeli | `common/models.py` vs `db/init.sql` | test spójności pada |
| Reguła w modelu bez id w froncie | `rules.py` vs `rules.ts` | test spójności pada |
| Zmiana frontu bez przebudowy demo | `demo/dashboard-static` nieaktualne | `scripts/check.sh` i CI padają |

</frozen-after-approval>

## Code Map

- `orchestrator/tests/test_consistency.py` -- strażnik spójności granic między projektami.
- `scraper/pyproject.toml`, `scraper/tests/test_logic.py` -- konfiguracja lintu i testy czystej logiki scrapera.
- `frontend/vite.config.ts` -- stałe nazwy plików tylko dla `build:demo`.
- `scripts/check.sh`, `.github/workflows/ci.yml` -- bramki lokalne i CI.

## Verification

- `scripts/check.sh` (ruff, pytest, typecheck, buildy, aktualność demo); `scripts/smoke.sh` po zmianach w grafie.
