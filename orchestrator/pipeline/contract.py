"""Kontrakt danych wejściowych v2 (warstwa landing w MinIO). Źródłem prawdy jest ten plik;
JSON Schema w `docs/intake-item.schema.json` jest z niego generowany (`python -m pipeline.contract`).

Obiekt landing jest niezmienny: `raw/{platform}/{external_id}/{hash12}.json`. Zmiana treści materiału = nowy obiekt
(nowa wersja dokumentu), nigdy nadpisanie. Źródło (scraper, demo, ręczne) zamienia się za adapterem, który pisze ten kształt.
"""

import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

MODULES = ("third_party_ads", "self_promotion", "non_investment_companies")
Module = Literal["third_party_ads", "self_promotion", "non_investment_companies"]


class Source(BaseModel):
    system: Literal["demo", "scraper", "manual"]
    platform: str = Field(min_length=1, description="youtube, telegram, web, tradingview, ...")
    external_id: str = Field(min_length=1, description="stabilny identyfikator materiału u źródła")
    url: str = Field(min_length=1)


class Advertiser(BaseModel):
    handle: str = Field(min_length=1, description="kanał, profil albo host strony")
    name: str | None = None
    url: str | None = None


class Observation(BaseModel):
    """Obserwowana para: podmiot publikujący i reklamowana firma ('' gdy nie dotyczy)."""

    advertiser: Advertiser
    advertised_firm: str = ""


class Image(BaseModel):
    key: str = Field(min_length=1, description="klucz obrazu w tym samym buckecie")
    sha256: str = Field(min_length=64, max_length=64)
    variant: Literal["desktop", "mobile", "tablet", "original"] = "original"
    focus: Literal["page", "risk"] = Field(
        "page", description="cała strona albo wycięty blok z informacją o ryzyku"
    )
    width: int | None = None
    height: int | None = None


class Manipulated(BaseModel):
    """Kontrolowany wariant testowy (nie prawdziwy materiał): które reguły miał zepsuć i jak."""

    rules: list[str]
    recipe: str


class IntakeItem(BaseModel):
    schema_version: Literal[2] = 2
    source: Source
    module: Module
    observation: Observation
    published_at: datetime | None = None
    captured_at: datetime
    title: str | None = None
    text: str | None = None
    lang: str | None = None
    images: list[Image] = []
    label: bool | None = Field(
        None, description="etykieta referencyjna (naruszenie), tylko dane testowe"
    )
    manipulated: Manipulated | None = None
    meta: dict = {}

    @model_validator(mode="after")
    def has_content(self):
        if not (self.text or self.images):
            raise ValueError("materiał musi mieć tekst albo obraz")
        return self

    @property
    def source_key(self) -> str:
        return f"{self.source.platform}:{self.source.external_id}"


def parse(raw: bytes) -> IntakeItem:
    return IntakeItem.model_validate(json.loads(raw))


if __name__ == "__main__":  # python -m pipeline.contract > ../docs/intake-item.schema.json
    print(json.dumps(IntakeItem.model_json_schema(), indent=2, ensure_ascii=False))
