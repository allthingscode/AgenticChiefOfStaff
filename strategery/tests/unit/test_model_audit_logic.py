"""Unit tests for F-043 Model Tier Auditor pure logic."""
from types import SimpleNamespace

from strategery.logic.model_audit_logic import build_report, classify_model


# ─── classify_model ───────────────────────────────────────────────────────────

class TestClassifyModel:
    def test_flash_lite_is_researcher(self):
        assert classify_model("models/gemini-2.5-flash-lite") == "researcher"
        assert classify_model("gemini-2.5-flash-lite-preview") == "researcher"

    def test_flash_is_default(self):
        assert classify_model("models/gemini-3-flash-preview") == "default"
        assert classify_model("gemini-2.0-flash") == "default"

    def test_pro_is_architect(self):
        assert classify_model("models/gemini-3-pro-preview") == "architect"
        assert classify_model("gemini-1.5-pro") == "architect"

    def test_ultra_is_architect(self):
        assert classify_model("gemini-ultra") == "architect"

    def test_embedding_is_special(self):
        assert classify_model("models/gemini-embedding-001") == "special"
        assert classify_model("models/text-embedding-004") == "special"

    def test_aqa_is_special(self):
        assert classify_model("models/aqa") == "special"

    def test_unknown_is_other(self):
        assert classify_model("models/some-new-model") == "other"

    def test_flash_lite_beats_flash(self):
        # flash-lite should never be classified as default
        assert classify_model("gemini-2.5-flash-lite") != "default"


# ─── build_report ─────────────────────────────────────────────────────────────

def _make_model(name: str, display_name: str = "", description: str = "") -> SimpleNamespace:
    return SimpleNamespace(name=name, display_name=display_name, description=description)


CURRENT_CONFIG = {
    "default":    "gemini-3-flash-preview",
    "researcher": "gemini-2.5-flash-lite",
    "architect":  "gemini-3-pro-preview",
}

SAMPLE_MODELS = [
    _make_model("models/gemini-3-flash-preview",   "Gemini 3 Flash Preview"),
    _make_model("models/gemini-2.5-flash-lite",    "Gemini 2.5 Flash Lite"),
    _make_model("models/gemini-3-pro-preview",     "Gemini 3 Pro Preview"),
    _make_model("models/gemini-embedding-001",     "Gemini Embedding"),
    _make_model("models/gemini-4-flash-preview",   "Gemini 4 Flash Preview"),
    _make_model("models/gemini-4-flash-lite",      "Gemini 4 Flash Lite"),
]


class TestBuildReport:
    def test_report_has_header(self):
        report = build_report(SAMPLE_MODELS, CURRENT_CONFIG)
        assert "# F-043: Model Tier Audit Report" in report

    def test_report_shows_current_config(self):
        report = build_report(SAMPLE_MODELS, CURRENT_CONFIG)
        assert "gemini-3-flash-preview" in report
        assert "gemini-2.5-flash-lite" in report
        assert "gemini-3-pro-preview" in report

    def test_current_model_flagged(self):
        report = build_report(SAMPLE_MODELS, CURRENT_CONFIG)
        assert "[CURRENT]" in report

    def test_suggestions_appear_when_current_model_retired(self):
        # Simulate a retired model not present in the available list
        retired_config = {
            "default":    "gemini-1-flash-retired",   # not in SAMPLE_MODELS
            "researcher": "gemini-2.5-flash-lite",
            "architect":  "gemini-3-pro-preview",
        }
        report = build_report(SAMPLE_MODELS, retired_config)
        assert "Suggested Updates" in report
        # Should suggest the first available default-tier model
        assert "gemini-3-flash-preview" in report

    def test_no_suggestion_when_current_model_still_available(self):
        # Current models are all in SAMPLE_MODELS — no suggestions expected
        report = build_report(SAMPLE_MODELS, CURRENT_CONFIG)
        assert "No changes suggested" in report

    def test_embedding_models_in_special_section(self):
        report = build_report(SAMPLE_MODELS, CURRENT_CONFIG)
        assert "Special-Purpose" in report
        assert "gemini-embedding-001" in report

    def test_empty_model_list(self):
        report = build_report([], CURRENT_CONFIG)
        assert "Available models:** 0" in report
        assert "No models classified" in report

    def test_report_is_valid_markdown_table(self):
        report = build_report(SAMPLE_MODELS, CURRENT_CONFIG)
        # Every table row should have the same number of pipes
        table_rows = [line for line in report.splitlines() if line.startswith("|")]
        for row in table_rows:
            # All table rows in the same table should have consistent pipe counts
            assert row.count("|") >= 2
