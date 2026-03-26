import json

from strategery.logic.reflection_logic import calculate_total_score, parse_json_response


def test_parse_json_response_clean():
    data = {"key": "value"}
    text = json.dumps(data)
    assert parse_json_response(text) == data

def test_parse_json_response_markdown():
    data = {"key": "value"}
    text = f"Here is the result:\n```json\n{json.dumps(data)}\n```\nHope this helps!"
    assert parse_json_response(text) == data

def test_parse_json_response_malformed():
    text = "Not JSON at all"
    assert parse_json_response(text) is None

def test_calculate_total_score():
    rubric = {
        "criteria": [
            {"name": "Accuracy", "weight": 2.0},
            {"name": "Completeness", "weight": 1.0}
        ]
    }
    # (0.8 * 2.0 + 1.0 * 1.0) / 3.0 = 2.6 / 3.0 = 0.867
    report = {
        "scores": [
            {"criterion_name": "Accuracy", "score": 0.8, "reasoning": "Fine"},
            {"criterion_name": "Completeness", "score": 1.0, "reasoning": "Perfect"}
        ]
    }
    score = calculate_total_score(report, rubric)
    assert score == 0.867

def test_calculate_total_score_missing_criterion():
    rubric = {
        "criteria": [
            {"name": "Accuracy", "weight": 1.0}
        ]
    }
    report = {
        "scores": [] # No scores provided
    }
    assert calculate_total_score(report, rubric) == 0.0
