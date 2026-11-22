"""Etap 3 grafu: oceny modułów AI (M1, M2, M3) zapisywane do Postgresa."""

import time

import dagster as dg

from pipeline import analyze, llm, store

RETRY = dg.RetryPolicy(max_retries=2, delay=5)


def _summary(score: float, details: dict) -> str:
    rules = details.get("rules")
    if rules is None:
        return f"score={score:.2f}"
    failed = [r for r, v in rules.items() if v is not None and v >= 0.6]
    return f"score={score:.2f}, naruszone reguły (>=0.6): {failed or 'brak'}"


def _score(
    context: dg.AssetExecutionContext, docs: list[dict], module: str, fn
) -> dg.MaterializeResult:
    """Liczy i zapisuje wyniki modułu, loguje każde wywołanie modelu (logi assetu + tabela model_calls).
    Błąd jednego dokumentu nie traci reszty; ponowienie pomija już policzone."""
    model = llm.model_id()
    done = store.done_ids(docs, model)
    errors, scores = [], {}
    originals = [d for d in docs if "duplicate_of" not in d]
    for d in originals:
        if d["id"] in done:
            continue
        started = time.monotonic()
        try:
            score, details = fn(d)
            ms = int((time.monotonic() - started) * 1000)
            store.save_result(d["id"], module, model, d["hash"], score, details)
            store.log_call(
                d["id"], module, model, analyze.state(d), {"score": score, **details}, score, ms
            )
            scores[d["key"]] = round(score, 2)
            context.log.info(f"{d['key']}: {_summary(score, details)} ({ms} ms, model {model})")
            for dup in (
                x for x in docs if x.get("duplicate_of") == d["id"] and x["id"] not in done
            ):
                store.save_result(
                    dup["id"],
                    module,
                    model,
                    dup["hash"],
                    score,
                    {**details, "duplicate_of": d["key"]},
                )
                scores[dup["key"]] = round(score, 2)
        except Exception as e:  # noqa: BLE001
            ms = int((time.monotonic() - started) * 1000)
            store.log_call(d["id"], module, model, analyze.state(d), None, None, ms, str(e)[:500])
            context.log.warning(f"{d['key']}: błąd po {ms} ms: {e}")
            errors.append(f"{d['key']}: {e}")
    meta = {"scored": len(scores), "scores": dg.MetadataValue.json(scores)}
    if errors:
        raise dg.Failure(
            description="; ".join(errors[:3]), metadata={**meta, "failed": len(errors)}
        )
    return dg.MaterializeResult(metadata={**meta, "documents": len(docs), "model": model})


@dg.asset(
    retry_policy=RETRY, description="Moduł 1: prawdopodobieństwo, że materiał jest reklamą (0-1)."
)
def ad_scores(
    context: dg.AssetExecutionContext, third_party_ads_docs: list[dict]
) -> dg.MaterializeResult:
    return _score(context, third_party_ads_docs, "third_party_ads", analyze.ad_score)


@dg.asset(
    retry_policy=RETRY,
    description="Moduł 2: 18 wyników reguł informacji o ryzyku (0-1 per reguła).",
)
def rule_scores(
    context: dg.AssetExecutionContext, self_promotion_docs: list[dict]
) -> dg.MaterializeResult:
    return _score(context, self_promotion_docs, "self_promotion", analyze.rules_scores)


@dg.asset(
    retry_policy=RETRY,
    description="Moduł 3: podejrzenie doradztwa inwestycyjnego bez uprawnień (0-1).",
)
def advisory_scores(
    context: dg.AssetExecutionContext, non_investment_docs: list[dict]
) -> dg.MaterializeResult:
    return _score(context, non_investment_docs, "non_investment_companies", analyze.advisory_score)
