import httpx
import pytest

from app.core import captcha
from app.core.config import Settings, settings
from app.core.errors import ApiError


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(settings, "captcha_provider", "arcaptcha")
    monkeypatch.setattr(settings, "arcaptcha_site_key", "public-site")
    monkeypatch.setattr(settings, "arcaptcha_secret_key", "private-test-secret")


def provider(monkeypatch, handler):
    client = httpx.Client
    monkeypatch.setattr(captcha.httpx, "Client", lambda **kw: client(transport=httpx.MockTransport(handler), **kw))


def test_disabled_does_not_call_provider(monkeypatch):
    monkeypatch.setattr(settings, "captcha_provider", "none")
    monkeypatch.setattr(captcha.httpx, "Client", lambda **kw: pytest.fail("Unexpected provider request"))
    captcha.verify_captcha(None)


def test_exact_official_contract_and_strict_success(enabled, monkeypatch):
    import json
    def handler(request):
        assert request.url == captcha.VERIFY_URL
        assert request.method == "POST"
        assert json.loads(request.content) == {"challenge_id":"token", "site_key":"public-site", "secret_key":"private-test-secret"}
        return httpx.Response(200, json={"success":True})
    provider(monkeypatch, handler)
    captcha.verify_captcha("token")


@pytest.mark.parametrize("body", [{"success":False}, {"success":"true"}, {"success":1}, {}, [], None])
def test_never_trust_truthy_or_missing_success(enabled, monkeypatch, body):
    provider(monkeypatch, lambda r: httpx.Response(200, json=body))
    with pytest.raises(ApiError) as error:captcha.verify_captcha("token")
    assert error.value.status == (400 if body == {"success":False} else 503)


@pytest.mark.parametrize("status,content", [(302,b""), (429,b""), (500,b"private-test-secret"), (200,b"not json"), (200,b"x"*16385)])
def test_http_redirect_corruption_and_size_fail_closed(enabled, monkeypatch, status, content):
    provider(monkeypatch, lambda r: httpx.Response(status, content=content, headers={"location":"https://other.example"}))
    with pytest.raises(ApiError) as error:captcha.verify_captcha("token")
    assert error.value.status == 503
    assert "private-test-secret" not in str(error.value)


def test_provider_timeout_fails_closed(enabled, monkeypatch):
    def handler(request):raise httpx.ConnectTimeout("private upstream details")
    provider(monkeypatch, handler)
    with pytest.raises(ApiError) as error:captcha.verify_captcha("token")
    assert error.value.status == 503 and "upstream" not in str(error.value)


def test_missing_keys_rejected_at_startup():
    with pytest.raises(ValueError):Settings(_env_file=None, captcha_provider="arcaptcha", arcaptcha_site_key="", arcaptcha_secret_key="")
    with pytest.raises(ValueError):Settings(_env_file=None, captcha_provider="unknown")


def test_runtime_missing_keys_fail_closed(enabled, monkeypatch):
    monkeypatch.setattr(settings, "arcaptcha_secret_key", "")
    with pytest.raises(ApiError) as error:captcha.verify_captcha("token")
    assert error.value.status == 503
