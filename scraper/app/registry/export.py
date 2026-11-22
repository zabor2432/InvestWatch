"""Write the registers to JSON files (same shape as docs/firm_registry): python -m app.registry.export <dir> [list ...]"""

import json
import sys
from datetime import date
from pathlib import Path

from investwatch_common.enums import RegistryList

from app.http import HttpClient
from app.log import configure
from app.registry import iscan, knf
from app.settings import settings

TITLES = {
    RegistryList.BROKERAGE_BANKS: "Banki prowadzące działalność maklerską",
    RegistryList.BROKERAGE_FIRMS: "Domy maklerskie",
    RegistryList.FOREIGN_BRANCHES: "Notyfikacje zagranicznych firm inwestycyjnych z państw UE/EOG - działalność w formie oddziału",
    RegistryList.FOREIGN_NO_BRANCH: "Notyfikacje zagranicznych firm inwestycyjnych z państw UE/EOG - działalność bez otwierania oddziału",
    RegistryList.CREDIT_INSTITUTIONS_BRANCHES: "Zestawienie notyfikacji dot. działalności instytucji kredytowych na terytorium RP poprzez oddział",
    RegistryList.CREDIT_INSTITUTIONS_CROSS_BORDER: "Zestawienie notyfikacji instytucji kredytowych na terytorium RP (działalność transgraniczna)",
    RegistryList.REVOKED_LICENCES: "Firmy inwestycyjne, którym cofnięto zezwolenie na prowadzenie działalności maklerskiej",
    RegistryList.KNF_PUBLIC_WARNINGS: "Lista ostrzeżeń publicznych KNF (sekcje dot. rynku kapitałowego)",
    RegistryList.ISCAN_WARNINGS: "IOSCO I-SCAN - ostrzeżenia regulatorów",
    RegistryList.AGENTS_LEGAL: "Agenci firm inwestycyjnych - osoby prawne i jednostki organizacyjne",
    RegistryList.AGENTS_NATURAL: "Agenci firm inwestycyjnych - osoby fizyczne",
}


def main(out_dir: Path, lists: list[RegistryList]) -> None:
    s = settings()
    http = HttpClient()
    out_dir.mkdir(parents=True, exist_ok=True)
    for lst in lists:
        if lst == RegistryList.ISCAN_WARNINGS:
            url, entries = iscan.URL, iscan.fetch(http, s.iscan_nca_ids, s.iscan_months)
            note = f"NCA_ID filter: {', '.join(s.iscan_nca_ids)}; validation date within the last {s.iscan_months} months."
        else:
            fl = knf.fetch_list(http, lst, s.knf_warning_sections)
            url, entries = fl.source_url, fl.entries
            note = (f"Sections kept: {'; '.join(s.knf_warning_sections)}" if lst == RegistryList.KNF_PUBLIC_WARNINGS
                    else "Parsed by scraper app.registry.knf; struck-through text stored in former_* fields.")
        meta = {"title_pl": TITLES[lst], "url": url, "source": "IOSCO" if lst == RegistryList.ISCAN_WARNINGS else
                "Komisja Nadzoru Finansowego (KNF)", "retrieved": date.today().isoformat(),
                "entry_count": len(entries), "complete": True, "note": note}
        path = out_dir / f"{lst.value}.json"
        path.write_text(json.dumps({"meta": meta, "entries": entries}, ensure_ascii=False, indent=2) + "\n")
        print(f"{path}: {len(entries)} entries")
    http.close()


if __name__ == "__main__":
    configure("WARNING")
    target = Path(sys.argv[1])
    chosen = [RegistryList(x) for x in sys.argv[2:]] or list(RegistryList)
    main(target, chosen)
