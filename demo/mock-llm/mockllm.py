"""Atrapa API System One (POST /v1/systemone) do testów bez klucza: heurystyki słów kluczowych."""
import json
import re
from http.server import BaseHTTPRequestHandler, HTTPServer


def p_yes(name: str, state: str) -> float:
    if name == "is_ad":
        return 0.96 if re.search(r"kod|link|polecam", state) else 0.04
    if name == "offers_advisory":
        return 0.94 if re.search(r"doradztwo|family office|rekomend", state) and "nie świadczymy" not in state else 0.05
    return 0.9 if name in ("2", "3", "17", "18") and re.search(r"zatwierdzon|bez wysiłku|regulaminie", state) else 0.1


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        state = str(body["state"]).lower()
        answers = {q: {"type": "noul", "noul": p_yes(q, state)} for q in body["questions"]}
        data = json.dumps({"model": "mock-llm", "answers": answers, "usage": {"input_tokens": 1, "output_tokens": 0}})
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(data.encode())

    def log_message(self, *args):
        pass


HTTPServer(("0.0.0.0", 5566), Handler).serve_forever()  # noqa: S104
