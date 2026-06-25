"""Tests for cortex_engine.api — the public interface."""
from cortex_engine.api import create_scan_request, LLMConfig
from cortex_engine.core.schemas import ScanRequest


class TestCreateScanRequest:
    def test_defaults(self):
        req = create_scan_request(repo="https://github.com/org/repo.git")
        assert req.repo == "https://github.com/org/repo.git"
        assert req.tiers == [1, 2]
        assert req.trigger == "api"
        assert req.full_scan is True
        assert req.report_formats == ["json", "pdf"]

    def test_custom_tiers(self):
        req = create_scan_request(repo=".", tiers=[1])
        assert req.tiers == [1]

    def test_pr_mode(self):
        req = create_scan_request(repo=".", pr_number=42, full_scan=False)
        assert req.pr_number == 42
        assert req.full_scan is False

    def test_cost_limit(self):
        req = create_scan_request(repo=".", cost_limit=5.0)
        assert req.cost_limit == 5.0

    def test_returns_scan_request(self):
        req = create_scan_request(repo=".")
        assert isinstance(req, ScanRequest)


class TestLLMConfig:
    def test_defaults(self):
        cfg = LLMConfig()
        assert cfg.provider == "vertex_ai"
        assert cfg.primary_model == "claude-opus-4-6"
        assert cfg.fallback_model == "claude-sonnet-4-6"
        assert cfg.max_retries == 3

    def test_anthropic_provider(self):
        cfg = LLMConfig(provider="anthropic", api_key="sk-test")
        assert cfg.provider == "anthropic"
        assert cfg.api_key == "sk-test"

    def test_vertex_config(self):
        cfg = LLMConfig(vertex_project_id="my-project", vertex_region="us-east5")
        assert cfg.vertex_project_id == "my-project"
        assert cfg.vertex_region == "us-east5"
