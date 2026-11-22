"""Ewaluacja modułu 2 na zebranych parach (oryginał, wariant zmanipulowany): czy celowo złamana reguła dostaje wysoki wynik
i czy wyskakuje względem oryginału. Czyta API backendu (stack musi być przetworzony tym modelem, który oceniamy).

    uv run python evaluate.py [--api http://localhost:8000] [--threshold 0.6]

Raport to tabela Markdown: per reguła liczba wariantów, odsetek wykrytych (wynik >= próg), średni wzrost wyniku względem
oryginału oraz odsetek fałszywych alarmów reguły na oryginałach (oryginały nie są oceniane przez nas jako naruszenia)."""

import argparse
import json
import urllib.request
from collections import defaultdict


def rule_scores(record: dict) -> dict[str, float]:
    return {
        r["rule_id"]: r["score"] for r in record.get("rule_results") or [] if r["verdict"] != "n/a"
    }


def source_key(record: dict) -> str:
    return next(e["value"] for e in record["evidence"] if e["kind"] == "snapshot")


def evaluate(records: list[dict], threshold: float = 0.6) -> dict:
    """-> {"rules": {rule: {n, detected, mean_gain}}, "originals": {n_rules, false_alarms}, "pairs": n}."""
    by_key = {source_key(r): r for r in records if r["module"] == 2}
    per_rule: dict[str, list[tuple[float, float]]] = defaultdict(list)
    pairs = 0
    for key, rec in by_key.items():
        if not rec["manipulated"] or "--" not in key:
            continue
        orig = by_key.get(key.split("--")[0])
        if orig is None:
            continue
        pairs += 1
        variant, base = rule_scores(rec), rule_scores(orig)
        for rule in rec.get("manipulated_rules", []):
            if rule in variant and rule in base:
                per_rule[rule].append((variant[rule], base[rule]))
    originals = [r for k, r in by_key.items() if "--" not in k and r["images"]]
    flags = [s >= threshold for r in originals for s in rule_scores(r).values()]
    return {
        "pairs": pairs,
        "rules": {
            rule: {
                "n": len(v),
                "detected": sum(a >= threshold for a, _ in v) / len(v),
                "mean_gain": sum(a - b for a, b in v) / len(v),
            }
            for rule, v in sorted(
                per_rule.items(),
                key=lambda kv: (int("".join(c for c in kv[0] if c.isdigit())), kv[0]),
            )
        },
        "originals": {"n_rules": len(flags), "false_alarms": sum(flags)},
    }


def markdown(result: dict, threshold: float) -> str:
    lines = [
        f"Pary (oryginał, wariant): {result['pairs']}, próg {threshold}",
        "",
        "| Reguła | Warianty | Wykryte | Średni wzrost wyniku |",
        "|---|---|---|---|",
    ]
    lines += [
        f"| {r} | {v['n']} | {v['detected']:.0%} | {v['mean_gain']:+.2f} |"
        for r, v in result["rules"].items()
    ]
    o = result["originals"]
    lines += [
        "",
        f"Fałszywe alarmy na oryginałach: {o['false_alarms']} z {o['n_rules']} ocenionych reguł",
    ]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--threshold", type=float, default=0.6)
    args = ap.parse_args()
    with urllib.request.urlopen(f"{args.api}/api/records?limit=5000", timeout=30) as r:  # noqa: S310  (adres lokalny z argumentu)
        records = json.load(r)["items"]
    print(markdown(evaluate(records, args.threshold), args.threshold))


if __name__ == "__main__":
    main()
