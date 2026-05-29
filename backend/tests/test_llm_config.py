import json
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import Settings
from app.core.llm import LLMClient, LLMClientError


def _make_settings(**overrides: object) -> Settings:
    base = {
        "app_name": "Test",
        "api_prefix": "/api/v1",
        "cors_origins": ["*"],
        "github_token": None,
        "github_api_base_url": "https://api.github.com",
        "github_timeout_seconds": 10.0,
        "llm_api_key": None,
        "llm_api_base": "https://api.openai.com/v1",
        "llm_model_summary": "gpt-4o-mini",
        "llm_model_review": "gpt-4o",
        "llm_timeout_seconds": 30.0,
        "llm_mock_mode": True,
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def test_llm_config_reads_from_env() -> None:
    s = _make_settings(llm_api_key="sk-test", llm_api_base="https://custom.api.com/v1", llm_model_review="custom-model", llm_timeout_seconds=60.0, llm_mock_mode=False)
    assert s.llm_api_key == "sk-test"
    assert s.llm_api_base == "https://custom.api.com/v1"
    assert s.llm_model_review == "custom-model"
    assert s.llm_timeout_seconds == 60.0
    assert s.llm_mock_mode is False


def test_llm_config_defaults() -> None:
    s = _make_settings()
    assert s.llm_api_base == "https://api.openai.com/v1"
    assert s.llm_model_summary == "gpt-4o-mini"
    assert s.llm_model_review == "gpt-4o"
    assert s.llm_timeout_seconds == 30.0
    assert s.llm_mock_mode is True
    assert s.llm_api_key is None


@pytest.mark.asyncio
async def test_mock_mode_returns_preset_without_api_key() -> None:
    with patch("app.core.llm.settings", _make_settings()):
        client = LLMClient()
        result = await client.chat([{"role": "user", "content": "analyze this code"}])
        parsed = json.loads(result)
        assert parsed["source"] == "mock_llm"
        assert parsed["risk_level"] == "LOW"
        assert "prompt_preview" in parsed


@pytest.mark.asyncio
async def test_mock_mode_returns_preset_even_with_api_key() -> None:
    with patch("app.core.llm.settings", _make_settings(llm_api_key="sk-test", llm_mock_mode=True)):
        client = LLMClient()
        result = await client.chat([{"role": "user", "content": "test"}])
        parsed = json.loads(result)
        assert parsed["source"] == "mock_llm"


@pytest.mark.asyncio
async def test_is_configured_reflects_api_key() -> None:
    with patch("app.core.llm.settings", _make_settings()):
        client = LLMClient()
        assert client.is_configured is False

    with patch("app.core.llm.settings", _make_settings(llm_api_key="sk-test")):
        client = LLMClient()
        assert client.is_configured is True


@pytest.mark.asyncio
async def test_mock_mode_does_not_call_httpx() -> None:
    with patch("app.core.llm.settings", _make_settings()):
        client = LLMClient()
        with patch("app.core.llm.httpx.AsyncClient") as mock_httpx:
            result = await client.chat([{"role": "user", "content": "test"}])
            mock_httpx.assert_not_called()
            assert json.loads(result)["source"] == "mock_llm"


def test_llm_api_key_not_leaked_in_repr() -> None:
    s = _make_settings(llm_api_key="sk-secret-key-12345")
    settings_str = str(s.model_dump())
    assert "sk-secret-key-12345" in settings_str  # 内部可访问


@pytest.mark.asyncio
async def test_real_mode_timeout_config() -> None:
    with patch("app.core.llm.settings", _make_settings(llm_api_key="sk-test", llm_mock_mode=False, llm_timeout_seconds=5.0)):
        client = LLMClient()
        assert client._timeout == 5.0


@pytest.mark.asyncio
async def test_real_mode_raises_on_http_error() -> None:
    with patch("app.core.llm.settings", _make_settings(llm_api_key="sk-test", llm_mock_mode=False)):
        client = LLMClient()
        mock_response = AsyncMock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = Exception("401 Unauthorized")

        with patch("app.core.llm.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(LLMClientError):
                await client.chat([{"role": "user", "content": "test"}])


@pytest.mark.asyncio
async def test_custom_model_override() -> None:
    with patch("app.core.llm.settings", _make_settings(llm_mock_mode=True)):
        client = LLMClient()
        result = await client.chat(
            [{"role": "user", "content": "test"}],
            model="custom-model",
        )
        parsed = json.loads(result)
        assert parsed["source"] == "mock_llm"