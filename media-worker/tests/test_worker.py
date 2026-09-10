import asyncio
import base64
import hashlib
import math
import struct
import sys
import time
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import worker


PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class StaticJwks:
    def get_signing_key_from_jwt(self, _token):
        class Key:
            key = PRIVATE_KEY.public_key()
        return Key()


def oidc_token(overrides=None):
    claims = {
        "iss": worker.OIDC_ISSUER,
        "aud": worker.OIDC_AUDIENCE,
        "sub": worker.OIDC_SUBJECT,
        "owner": "soldioms-projects",
        "project": "sanad",
        "environment": "production",
        "iat": 1_700_000_000,
        "exp": 1_900_000_000,
    }
    claims.update(overrides or {})
    return jwt.encode(claims, PRIVATE_KEY, algorithm="RS256", headers={"kid": "test"})


def body(data=b"\xff\xd8\xff\xd9", **overrides):
    result = {
        "media_base64": base64.b64encode(data).decode(),
        "digest": hashlib.sha256(data).hexdigest(),
        "mime": "image/jpeg",
        "kind": "image",
        "scope": "original_media",
    }
    result.update(overrides)
    return result


@pytest.fixture(autouse=True)
def isolated_globals(monkeypatch):
    monkeypatch.setattr(worker, "jwks_client", StaticJwks())
    monkeypatch.setattr(worker, "unknown_kids", worker.UnknownKidCache())
    monkeypatch.setattr(worker, "preauth_rate_limiter", worker.SlidingWindowRateLimiter(100))
    monkeypatch.setattr(worker, "rate_limiter", worker.SlidingWindowRateLimiter(100))
    monkeypatch.setattr(worker, "daily_budget", worker.DailyCallBudget(100))
    monkeypatch.setattr(worker, "analysis_semaphore", asyncio.Semaphore(2))


def test_oidc_requires_exact_issuer_audience_and_subject():
    assert worker.verify_vercel_oidc(oidc_token())["sub"] == worker.OIDC_SUBJECT
    for claims in (
        {"iss": "https://oidc.vercel.com/other"},
        {"aud": "https://vercel.com/other"},
        {"sub": "owner:soldioms-projects:project:sanad:environment:preview"},
        {"owner": "other"},
        {"project": "other"},
        {"environment": "preview"},
    ):
        with pytest.raises(Exception) as failure:
            worker.verify_vercel_oidc(oidc_token(claims))
        assert failure.value.status_code in (401, 403)


def test_unknown_jwt_kid_is_negatively_cached():
    token = oidc_token()

    class MissingKid:
        calls = 0

        def get_signing_key_from_jwt(self, _token):
            self.calls += 1
            raise jwt.PyJWKClientError("missing")

    client = MissingKid()
    for _ in range(2):
        with pytest.raises(Exception):
            worker.verify_vercel_oidc(token, client=client)
    assert client.calls == 1


def test_analyze_rejects_missing_token_malformed_payload_and_bad_digest():
    client = TestClient(worker.app)
    assert client.post("/analyze", json=body()).status_code == 401
    assert client.post("/analyze", headers={"Authorization": "Bearer nope"}, json=body()).status_code == 401
    headers = {"Authorization": f"Bearer {oidc_token()}"}
    assert client.post("/analyze", headers=headers, json=body(media_base64="not base64")).status_code == 422
    assert client.post("/analyze", headers=headers, json=body(digest="0" * 64)).status_code == 422
    assert client.post("/analyze", headers=headers, json=body(mime="image/png")).status_code == 415


def test_hard_body_cap_does_not_echo_or_retain_media():
    client = TestClient(worker.app)
    raw = b"x" * (worker.MAX_BODY_BYTES + 1)
    response = client.post("/analyze", content=raw, headers={"content-type": "application/json"})
    assert response.status_code == 413
    assert "x" * 100 not in response.text
    assert response.headers["cache-control"] == "no-store"


def test_preauthentication_rate_limit_runs_before_jwks():
    worker.preauth_rate_limiter = worker.SlidingWindowRateLimiter(1)
    client = TestClient(worker.app)
    assert client.post("/analyze", json=body()).status_code == 401
    assert client.post("/analyze", json=body()).status_code == 429


def test_capacity_rejection_does_not_consume_daily_allowance(monkeypatch):
    monkeypatch.setattr(worker, "verify_vercel_oidc", lambda _token: {"sub": worker.OIDC_SUBJECT})
    monkeypatch.setattr(worker, "analysis_semaphore", asyncio.Semaphore(0))
    budget = worker.DailyCallBudget(100)
    monkeypatch.setattr(worker, "daily_budget", budget)
    client = TestClient(worker.app)
    response = client.post(
        "/analyze",
        headers={"Authorization": f"Bearer {oidc_token()}"},
        json=body(),
    )
    assert response.status_code == 503
    assert budget.calls == 0


def test_verdict_gates_and_required_contract_fields():
    payload = worker.AnalyzeRequest(**body())
    common = {
        "confidence": 0.8, "deepfake_risk_code": "low", "conflicts": False,
        "signals_for": ["Model observation."],
        "signals_against": ["Concrete manipulation artifact."],
        "limitations": [],
    }
    real = worker.build_result(payload, 4, ["Decoded JPEG image dimensions: 1x1."], False, {}, {
        **common, "verdict": "likely_real", "manipulation_concern": False,
    })
    assert real["verdict"] == "likely_real"
    assert real["verdict_label_en"] == "No clear manipulation indicators detected"
    assert real["deepfake_risk"] == "منخفض"
    assert real["provider"] == "gemini"
    assert real["bytes_analyzed"] == 4
    manipulated = worker.build_result(payload, 4, ["Editing software metadata."], True, {}, {
        **common, "verdict": "likely_manipulated", "manipulation_concern": True,
    })
    assert manipulated["verdict"] == "likely_manipulated"
    insufficient = worker.build_result(payload, 4, [], False, {}, {
        **common, "verdict": "likely_real", "manipulation_concern": False,
    })
    assert insufficient["verdict"] == "insufficient"
    assert insufficient["confidence"] is None
    low_confidence = worker.build_result(payload, 4, ["Decoded image."], False, {}, {
        **common, "verdict": "likely_real", "confidence": 0.3,
        "manipulation_concern": False,
    })
    assert low_confidence["verdict"] == "insufficient"


def test_generic_encoder_is_not_independent_manipulation_evidence():
    assert worker.has_editing_marker("Lavf61.7.100") is False
    assert worker.has_editing_marker("Adobe Premiere Pro") is True


def test_extreme_video_dimensions_are_rejected_before_frame_decode(monkeypatch):
    monkeypatch.setattr(worker, "_ffprobe", lambda _path: {
        "format": {"duration": "1.0"},
        "streams": [{
            "codec_type": "video", "codec_name": "h264",
            "width": 100_000, "height": 100_000,
        }],
    })
    called = False

    def run(*_args, **_kwargs):
        nonlocal called
        called = True
        return 0, "", ""

    monkeypatch.setattr(worker, "_run", run)
    with pytest.raises(Exception) as failure:
        worker.inspect_video(b"video", ".mp4")
    assert failure.value.status_code == 415
    assert called is False


def test_gemini_output_schema_rejects_malformed_or_extra_content():
    valid = {
        "verdict": "likely_real", "confidence": 0.8, "deepfake_risk_code": "low",
        "manipulation_concern": False, "conflicts": False,
        "signals_for": [], "signals_against": [], "limitations": [],
    }
    assert worker.GeminiResponse.model_validate(valid).verdict == "likely_real"
    with pytest.raises(Exception):
        worker.GeminiResponse.model_validate({**valid, "unexpected": "field"})
    with pytest.raises(Exception):
        worker.GeminiResponse.model_validate({**valid, "confidence": "certain"})


def test_gemini_uses_structured_json_with_a_mocked_client():
    payload = worker.AnalyzeRequest(**body())
    response_json = {
        "verdict": "likely_real", "confidence": 0.8, "deepfake_risk_code": "low",
        "manipulation_concern": False, "conflicts": False,
        "signals_for": [], "signals_against": [], "limitations": [],
    }
    captured = {}

    class Models:
        def generate_content(self, **kwargs):
            captured.update(kwargs)
            return type("Response", (), {"text": __import__("json").dumps(response_json)})()

    result = worker.ask_gemini(payload, b"\xff\xd8\xff\xd9", {"format": "JPEG"}, [], type("Client", (), {"models": Models()})())
    assert result == response_json
    assert captured["config"].response_mime_type == "application/json"
    assert captured["config"].model_dump()["response_schema"] is not None


def test_gemini_client_has_bounded_http_timeout(monkeypatch):
    payload = worker.AnalyzeRequest(**body())
    captured = {}

    class Models:
        def generate_content(self, **_kwargs):
            return type("Response", (), {"text": __import__("json").dumps({
                "verdict": "insufficient", "confidence": 0.0,
                "deepfake_risk_code": "unknown", "manipulation_concern": False,
                "conflicts": False, "signals_for": [], "signals_against": [],
                "limitations": [],
            })})()

    def client(**kwargs):
        captured.update(kwargs)
        return type("Client", (), {"models": Models()})()

    monkeypatch.setattr(worker.genai, "Client", client)
    worker.ask_gemini(payload, b"\xff\xd8\xff\xd9", {"format": "JPEG"}, [])
    assert captured["http_options"].timeout == worker.GEMINI_TIMEOUT_MS


def test_gemini_refusal_becomes_explicit_provider_refusal():
    payload = worker.AnalyzeRequest(**body())

    class Response:
        prompt_feedback = type("Feedback", (), {"block_reason": "SAFETY"})()

        @property
        def text(self):
            raise ValueError("blocked")

    class Models:
        def generate_content(self, **_kwargs):
            return Response()

    with pytest.raises(worker.ProviderRefused):
        worker.ask_gemini(payload, b"\xff\xd8\xff\xd9", {"format": "JPEG"}, [], type("Client", (), {"models": Models()})())


def test_worker_deadline_returns_explicit_timeout(monkeypatch):
    monkeypatch.setattr(worker, "verify_vercel_oidc", lambda _token: {"sub": worker.OIDC_SUBJECT})
    monkeypatch.setattr(worker, "GEMINI_DEADLINE_SECONDS", 0.01)
    monkeypatch.setattr(worker, "run_deterministic_checks", lambda *_: (
        {"format": "JPEG"}, ["Decoded image."], False, {"mode": "test"}, [],
    ))

    def slow(*_args, **_kwargs):
        time.sleep(0.05)
        return {}

    monkeypatch.setattr(worker, "ask_gemini", slow)
    client = TestClient(worker.app)
    response = client.post(
        "/analyze",
        headers={"Authorization": f"Bearer {oidc_token()}"},
        json=body(),
    )
    assert response.status_code == 200
    assert response.json()["provider_status"] == "provider_timeout"


def test_bounded_audio_spectral_fact_is_deterministic():
    pcm = struct.pack(
        "<1024h",
        *(int(10_000 * math.sin(2 * math.pi * 1_000 * index / 8_000)) for index in range(1024)),
    )
    centroid = worker._spectral_centroid_hz(pcm)
    assert centroid is not None
    assert 900 <= centroid <= 1_100


@pytest.mark.parametrize(
    ("kind", "mime", "sampling_mode"),
    [
        ("video", "video/mp4", "representative-frames"),
        ("audio", "audio/mpeg", "bounded-audio-facts"),
    ],
)
@pytest.mark.parametrize(
    ("provider_error", "expected_status"),
    [(RuntimeError("offline"), "provider_failed"), (worker.ProviderRefused(), "provider_refused")],
)
def test_scoped_video_audio_fallbacks_without_provider(
    monkeypatch, kind, mime, sampling_mode, provider_error, expected_status
):
    monkeypatch.setattr(worker, "run_deterministic_checks", lambda *_: (
        {"codec": "h264"}, ["Decoded video stream."], False,
        {"mode": sampling_mode, "timestamps_seconds": [0]}, [],
    ))
    monkeypatch.setattr(worker, "ask_gemini", lambda *_: (_ for _ in ()).throw(provider_error))
    client = TestClient(worker.app)
    response = client.post("/analyze", headers={"Authorization": f"Bearer {oidc_token()}"}, json=body(
        kind.encode(), kind=kind, mime=mime, scope="embedded_media",
    ))
    assert response.status_code == 200
    assert response.json()["verdict"] == "insufficient"
    assert response.json()["provider_status"] == expected_status
    assert response.json()["sampling"]["mode"] == sampling_mode


def test_worker_source_has_no_logging_or_token_retention():
    source = Path(worker.__file__).read_text(encoding="utf-8")
    assert "logging." not in source
    assert "print(" not in source
    assert "f\"token:" not in source
