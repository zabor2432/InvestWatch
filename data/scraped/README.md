# Zebrane dane (eksporty scrapera)

Każdy katalog to jeden eksport: posty z trzech modułów razem z trafieniami (`post_hits`), wersjami treści,
metadanymi mediów, jobami scrapera i plikami mediów (zrzuty ekranu, obrazy, miniatury).

| Plik | Zawartość |
|---|---|
| `manifest.json` | data eksportu, liczba postów, jobów i plików |
| `posts.jsonl` | jeden post na linię, z polami `hits`, `versions`, `media` |
| `jobs.jsonl` | joby scrapera (`scrape_jobs`) |
| `media/<klucz>` | pliki z MinIO, ścieżka = `media.object_key` |

## Wgranie do własnych kontenerów

```bash
# 1. kontenery muszą działać (baza po migracjach, MinIO)
docker compose up -d --build db migrations redis minio searxng scraper scraper-worker

# 2. import (zastąp 2026-11-22 nazwą katalogu)
docker compose run --rm --no-deps -v ./data:/data scraper python -m app.dataset import /data/scraped/2026-11-22
```

Wynik to np. `{"jobs": 30, "posts": 17, "posts_skipped": 0, "media_files": 42}`. Import można powtarzać:
posty, które już są w bazie (ta sama platforma i `external_id`), są pomijane. Dane obejrzysz pod http://localhost:8001/browse.

Rejestru firm (`firms`) nie ma w eksporcie: każdy kontener tworzy go sam przy pierwszym `registry_sync`
(z plików `docs/firm_registry`).

## Do pipeline'u InvestWatch (MinIO, kontrakt v2)

Próbki z tego katalogu trafiają do bucketa `investwatch` **automatycznie** przy `docker compose up` (usługa `seed`, ten sam kod co adapter scrapera:
`common/investwatch_common/landing.py`). Ręcznie, z bazy scrapera albo z eksportu:

```bash
curl -X POST localhost:8001/landing/sync
docker compose run --rm --no-deps -v ./data:/data scraper python -m app.landing from-export /data/scraped/2026-11-22
```

Ponowne uruchomienie niczego nie duplikuje (obiekty i obrazy adresowane treścią). Potem **Odśwież dane** w dashboardzie.

## Nowy eksport

```bash
mkdir -p data/scraped
docker compose run --rm --no-deps -v ./data:/data scraper python -m app.dataset export /data/scraped/$(date +%F)
```
