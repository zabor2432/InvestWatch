"""Wejście Dagstera: składa assety trzech etapów w jedną definicję.

intake_items -> documents -> analysis_batch (pipeline/ingest.py)
-> transcribed_batch (opcjonalny) -> preprocessed_batch -> split po `module` (pipeline/prepare.py)
-> ad_scores / rule_scores / advisory_scores -> Postgres (pipeline/scoring.py)

Nic nie uruchamia się samo: batch startuje ręcznie z UI Dagstera albo z przycisku "Odśwież dane" w aplikacji (job process_batch)."""

import dagster as dg

from pipeline.ingest import analysis_batch, documents, intake_items
from pipeline.prepare import module_splits, preprocessed_batch, transcribed_batch
from pipeline.scoring import ad_scores, advisory_scores, rule_scores

process_batch = dg.define_asset_job("process_batch", selection=dg.AssetSelection.all())

defs = dg.Definitions(
    assets=[
        intake_items,
        documents,
        analysis_batch,
        transcribed_batch,
        preprocessed_batch,
        module_splits,
        ad_scores,
        rule_scores,
        advisory_scores,
    ],
    jobs=[process_batch],
)
