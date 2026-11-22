"""Uruchamianie przetwarzania w Dagsterze (GraphQL): przycisk "Odśwież dane" w aplikacji."""

import os

import httpx

JOB = {
    "repositoryLocationName": "pipeline.definitions",
    "repositoryName": "__repository__",
    "jobName": "process_batch",
}
ACTIVE = ["QUEUED", "NOT_STARTED", "STARTING", "STARTED"]

LAUNCH = """mutation($sel: JobOrPipelineSelector!) { launchRun(executionParams: {selector: $sel}) {
  __typename ... on LaunchRunSuccess { run { runId } } ... on PythonError { message } } }"""
ACTIVE_RUN = """query($f: RunsFilter!) { runsOrError(filter: $f, limit: 1) {
  __typename ... on Runs { results { runId status } } } }"""
RUN = """query($id: ID!) { runOrError(runId: $id) { __typename ... on Run { runId status } } }"""


class DagsterError(RuntimeError):
    pass


def _gql(query: str, variables: dict, client: httpx.Client | None = None) -> dict:
    url = os.environ.get("DAGSTER_GRAPHQL_URL", "http://dagster-webserver:3000/graphql")
    try:
        r = (client or httpx).post(url, json={"query": query, "variables": variables}, timeout=15)
        r.raise_for_status()
        body = r.json()
    except (httpx.HTTPError, ValueError) as e:
        raise DagsterError(f"Dagster niedostępny: {e}") from None
    if body.get("errors"):
        raise DagsterError(body["errors"][0]["message"])
    return body["data"]


def start(client: httpx.Client | None = None) -> dict:
    """Uruchamia process_batch; gdy run już trwa, zwraca jego id (bez dublowania). -> {run_id, status, already_running}"""
    data = _gql(ACTIVE_RUN, {"f": {"pipelineName": "process_batch", "statuses": ACTIVE}}, client)
    runs = data["runsOrError"].get("results", [])
    if runs:
        return {"run_id": runs[0]["runId"], "status": runs[0]["status"], "already_running": True}
    res = _gql(LAUNCH, {"sel": JOB}, client)["launchRun"]
    if res["__typename"] != "LaunchRunSuccess":
        raise DagsterError(res.get("message") or res["__typename"])
    return {"run_id": res["run"]["runId"], "status": "QUEUED", "already_running": False}


def status(run_id: str, client: httpx.Client | None = None) -> dict | None:
    run = _gql(RUN, {"id": run_id}, client)["runOrError"]
    return {"run_id": run["runId"], "status": run["status"]} if run["__typename"] == "Run" else None
