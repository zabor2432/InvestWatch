import evaluate


def rec(key, scores, manipulated=False, rules=(), images=True):
    return {
        "module": 2,
        "evidence": [{"kind": "snapshot", "value": key}],
        "manipulated": manipulated,
        "manipulated_rules": list(rules),
        "images": [{}] if images else [],
        "rule_results": [
            {"rule_id": r, "verdict": "n/a" if s is None else "pass", "score": s or 0.0}
            for r, s in scores.items()
        ],
    }


def test_detection_gain_and_false_alarms_per_rule():
    records = [
        rec("web:a", {"4": 0.1, "5": 0.7, "6": None}),  # oryginał z jednym fałszywym alarmem (5)
        rec("web:a--tiny_print", {"4": 0.9, "5": 0.7, "6": None}, True, ["4"]),
        rec("web:b", {"4": 0.2, "5": 0.1}),
        rec("web:b--tiny_print", {"4": 0.3, "5": 0.1}, True, ["4"]),  # niewykryty
        rec("web:c--blurred", {"5": 0.9}, True, ["5"]),  # brak oryginału: pomijamy
        {**rec("instagram:x", {"3": 0.9}), "module": 1},
    ]
    out = evaluate.evaluate(records, threshold=0.6)
    assert out["pairs"] == 2
    assert out["rules"]["4"]["n"] == 2 and out["rules"]["4"]["detected"] == 0.5
    assert round(out["rules"]["4"]["mean_gain"], 2) == 0.45  # (0.8 + 0.1) / 2
    assert out["originals"] == {"n_rules": 4, "false_alarms": 1}  # n/a nie liczy się jako ocena
    assert "| 4 | 2 | 50% | +0.45 |" in evaluate.markdown(out, 0.6)
