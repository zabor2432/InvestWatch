"""Logika AI modułów 1-3 (bez Dagstera). Każda funkcja zwraca (score 0-1, details).

Dokument ma listę obrazów `doc["images"]` = [{variant, focus, uri}]: wariant ekranu (original/desktop/tablet/mobile) i ostrość
(`page` = cała strona, `risk` = wycięty blok z informacją o ryzyku)."""

from pipeline import images, llm
from pipeline.rules import FOOTER_ONLY, RULES, SPEC, VISUAL, VISUAL_QUESTIONS

PAGE_ORDER = ("original", "desktop", "tablet", "mobile")


def _pick(doc: dict, focus: str, variants: tuple[str, ...] = PAGE_ORDER) -> str | None:
    """Pierwszy obraz o danej ostrości, w kolejności preferencji wariantów."""
    for variant in variants:
        for img in doc.get("images", []):
            if img["variant"] == variant and img["focus"] == focus:
                return img["uri"]
    return None


def state(doc: dict) -> str:
    """Dokładnie to, co wysyłamy do modelu jako `state`."""
    attached = ", ".join(f"{i['variant']}/{i['focus']}" for i in doc.get("images", []))
    note = f"\n(Do materiału dołączono obrazy: {attached}.)" if attached else ""
    title = f"Tytuł: {doc['title']}\n" if doc.get("title") else ""
    return f"Źródło: {doc['source_url']}\n{title}Treść: {doc['text'] or '(brak tekstu)'}{note}"


def _images(doc: dict) -> list[str] | None:
    """Główny obraz materiału (cała strona, a gdy jej nie ma, blok z ryzykiem)."""
    main = _pick(doc, "page") or _pick(doc, "risk")
    return [images.full(main)] if main else None


def ad_score(doc: dict) -> tuple[float, dict]:
    """Moduł 1: czy materiał (np. wpis influencera) jest reklamą produktów/usług finansowych."""
    a = llm.classify(
        state(doc),
        {
            "is_ad": "Materiał jest reklamą lub promocją produktów albo usług finansowych "
            "(także ukrytą: kod rabatowy, link afiliacyjny, polecenie konkretnej firmy)."
        },
        _images(doc),
    )
    return a["is_ad"], {}


def _responsive_pair(doc: dict) -> list[str] | None:
    """Ta sama reklama na komputerze i telefonie: bloki z ryzykiem, a bez nich całe strony."""
    for focus in ("risk", "page"):
        desktop, mobile = _pick(doc, focus, ("desktop",)), _pick(doc, focus, ("mobile",))
        if desktop and mobile:
            return [images.full(desktop), images.full(mobile)]
    return None


def rules_scores(doc: dict) -> tuple[float, dict]:
    """Moduł 2: 18 reguł (2-18 z 12a/12b). Wynik reguły = P(naruszenie); None = nie dotyczy.
    Reguły merytoryczne: jedno żądanie (tekst + główny obraz). Reguły wizualne (4, 5, 6) tylko z obrazem,
    osobno i na bloku z ryzykiem (albo wycinku stopki). Reguła 8 wymaga pary komputer/telefon.
    Score rekordu = najgorsza reguła."""
    rules = dict.fromkeys(RULES)
    semantic = {
        r: {
            "instructions": f"Wymóg „{name}” (załącznik UKNF): {SPEC[r]} Czy materiał NARUSZA ten wymóg?",
            "criteria": {"true": bad, "false": good},
        }
        for r, (name, bad, good) in RULES.items()
        if r not in VISUAL
    }
    rules |= llm.classify(state(doc), semantic, _images(doc))
    page, risk = _pick(doc, "page"), _pick(doc, "risk")
    if page or risk:
        scene = "Zrzut reklamy firmy inwestycyjnej."
        footer = images.full(risk) if risk else images.footer(page)
        rules |= llm.classify(scene, {r: VISUAL_QUESTIONS[r] for r in FOOTER_ONLY}, [footer])
        rules |= llm.classify(
            scene, {"4": VISUAL_QUESTIONS["4"]}, [images.full(page or risk), footer]
        )
    pair = _responsive_pair(doc)
    if pair:
        scene = "Porównanie wyświetlenia tej samej reklamy firmy inwestycyjnej na komputerze i telefonie."
        rules |= llm.classify(scene, {"8": VISUAL_QUESTIONS["8"]}, pair)
    return max((s for s in rules.values() if s is not None), default=0.0), {"rules": rules}


def advisory_score(doc: dict) -> tuple[float, dict]:
    """Moduł 3: czy podmiot (niebędący firmą inwestycyjną) oferuje doradztwo inwestycyjne."""
    a = llm.classify(
        state(doc),
        {
            "offers_advisory": "Firma oferuje usługi doradztwa inwestycyjnego, zarządzania majątkiem "
            "(wealth management, family office) lub rekomenduje konkretne inwestycje."
        },
        _images(doc),
    )
    return a["offers_advisory"], {}
