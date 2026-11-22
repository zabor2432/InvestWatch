# TODO frontend

- [ ] Paginacja i filtrowanie po stronie serwera (dziś całość pobierana jednym `GET /api/records`).
- [x] Podpięcie prawdziwego backendu (obraz Dockera: `VITE_USE_MOCKS=false`; mocki tylko w `npm run dev`).
- [ ] Eksport wyników (CSV) i raport per moduł.
- [ ] Prawdziwe etykiety referencyjne do kalibracji, gdy dostępne będą próbki danych.
- [ ] Wykresy w widoku Przegląd liczą po stronie klienta na pełnej liście; przy paginacji serwerowej przenieść agregaty do `GET /api/stats`.
