# TODO (pipeline / moduł 2)

## Preprocessing obrazów pod reguły wizualne

Zasada: tekst ocenia LLM, a to, co typowo "obrazowe", mierzymy deterministycznie i wynik podajemy modelowi jako
tekst w `state` (albo używamy go wprost jako score). Dziś: konkretne pytania wizualne na wycinku stopki
(`images.py`, `FOOTER_FRACTION`), a reguła 8 działa tylko dla rekordu z parą obrazów desktop/mobile.

| Reguła | Pomiar do zrobienia |
|---|---|
| 4 rozmiar czcionki ryzyka | OCR z bounding boxami; wysokość znaków bloku z ryzykiem vs przeważająca wysokość w materiale |
| 5 ekspozycja i kontrast | kontrast WCAG tekst/tło w bloku z ryzykiem; rozmycie (wariancja Laplasjanu); przesłonięcie innymi elementami |
| 6 ukrywanie | pozycja bloku (dolne X%, poza kadrem, przypis), kolor zbliżony do tła |
| 8 responsywność | model porównuje parę desktop/mobile (zrobione); pomiar deterministyczny: ucięcie bloku z ryzykiem poza viewportem na 390 px (wymaga DOM) |
| 13 dominacja wyników | powierzchnia i wielkość znaków wyników historycznych vs ostrzeżeń |
| 7 jedno kliknięcie | wymaga DOM (elementy rozwijane, linki), nie obrazu |

- Narzędzia: OCR (RapidOCR lub Tesseract), Pillow/numpy.
- Test regresji: para XTB (`demo/real/`, oryginał vs nieczytelne ryzyko). Reguła 5 ma wyjść niska vs wysoka.
- Reguły merytoryczne na obrazach (2, 3, 9-18) nie były jeszcze mierzone po zmianie na konkretne pytania.

## Progi per reguła

Zrobione: próg globalny (domyślnie 0.5) i nadpisania per reguła M2 w przeglądarce, sugestia z ocen analityków (maks. F1), panel w Kalibracji.
Do zrobienia:
- Zapis progów na serwerze (tabela, audyt zmian), wspólne dla zespołu; dziś każdy ma własne w `localStorage`.
- Sugestie na prawdziwych ocenach (dane demo są wygenerowane): zebrać zgodne materiały i oceny, sprawdzić stabilność sugestii przy małej próbce.
- Agregat rekordu M2 to maksimum z reguł; rozważyć wagi reguł (dziś reguła 4 flaguje najwięcej).

## Inne

- Oceny ręczne (`annotations`) mogą zasilić `ground_truth` i progi per reguła (konsensus oceniających jako etykieta).
- Tryb ślepy ukrywa wyniki w szczegółach i w kolumnie "Ryzyko", ale filtry (ryzyko, próg) i sortowanie nadal zdradzają kolejność.
- **Scraper** (`docs/scraper-integration.md`): adapter działa; do zrobienia: przekazanie `raw.layout` i bloków z ryzykiem (`focus: risk`) do kontraktu, firma M1 z treści a nie z zapytania, mierzenie reguł M2 deterministycznie na układzie.
- **Ewaluacja na zebranym zbiorze**: `demo/collect/evaluate.py` (wykrycie celowo złamanej reguły, fałszywe alarmy na oryginałach) dla prawdziwego modelu; wyniki zapisać w dokumentacji.
- Retencja `raw/` (TTL) i trwałe `evidence/` z architektury nie są zaimplementowane.
- Model lokalny: profil Compose z serwerem OpenJev na GPU (dziś tylko zmiana `TYPESAFE_BASE_URL`); potwierdzić licencję wag z UKNF (pytanie 15).
- Prezentacja PDF, tytuł i opis projektu, opcjonalnie film (wymagania formalne §4).
- Opcjonalnie: SonarCloud/CodeQL (wymagają konta, tokenu lub publicznego repo), SBOM CycloneDX; pierwszy przebieg CI na GitHubie i ewentualne podbicie wersji akcji.
- Embeddingi i deduplikacja semantyczna (odstępstwo od §3.2, dziś tylko hash).
