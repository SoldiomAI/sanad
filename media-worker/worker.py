"""Bounded, authenticated media-forensics worker for SANAD.

The worker intentionally provides conservative evidence, not an authenticity
determination.  It receives direct bytes only and never persists request media,
bearer tokens, or remote URLs.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import hmac
import json
import math
import os
import re
import struct
import subprocess
import tempfile
import threading
from collections import defaultdict, deque
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from typing import Any, Callable, Literal

import jwt
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from google import genai
from google.genai import types
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_MEDIA_BYTES = 6 * 1024 * 1024
MAX_BASE64_CHARS = ((MAX_MEDIA_BYTES + 2) // 3) * 4
MAX_BODY_BYTES = 9 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
MAX_VIDEO_DURATION_SECONDS = 30 * 60
MAX_VIDEO_DIMENSION = 8192
MAX_VIDEO_PIXELS = 40_000_000
MAX_VIDEO_ASPECT_RATIO = 16
MAX_AUDIO_ANALYSIS_SECONDS = 120
MAX_FRAME_BYTES = 1 * 1024 * 1024
GEMINI_TIMEOUT_MS = 40_000
GEMINI_DEADLINE_SECONDS = 45
JWKS_URL = "https://oidc.vercel.com/soldioms-projects/.well-known/jwks"
OIDC_ISSUER = "https://oidc.vercel.com/soldioms-projects"
OIDC_AUDIENCE = "https://vercel.com/soldioms-projects"
OIDC_SUBJECT = "owner:soldioms-projects:project:sanad:environment:production"
WORKER_VERSION = os.getenv("WORKER_VERSION", "dev")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")

MIMES_BY_KIND = {
    "image": {"image/jpeg": ".jpg", "image/png": ".png"},
    "video": {"video/mp4": ".mp4", "video/webm": ".webm"},
    "audio": {
        "audio/mpeg": ".mp3",
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/ogg": ".ogg",
        "audio/mp4": ".m4a",
    },
}
DIRECT_SCOPES = {"original_media", "embedded_media"}
EDITING_MARKERS = (
    "adobe", "after effects", "capcut", "comfyui", "elevenlabs", "firefly",
    "midjourney", "photoshop", "runway", "stable diffusion", "synthesia",
)
ARABIC_RISK = {
    "low": "منخفض",
    "moderate": "متوسط",
    "high": "مرتفع",
    "unknown": "غير مقيّم",
}
PROVIDER_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {
            "type": "string",
            "enum": ["likely_real", "likely_manipulated", "insufficient"],
        },
        "confidence": {"type": "number"},
        "deepfake_risk_code": {
            "type": "string",
            "enum": ["low", "moderate", "high", "unknown"],
        },
        "manipulation_concern": {"type": "boolean"},
        "conflicts": {"type": "boolean"},
        "signals_for": {"type": "array", "items": {"type": "string"}},
        "signals_against": {"type": "array", "items": {"type": "string"}},
        "limitations": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "verdict",
        "confidence",
        "deepfake_risk_code",
        "manipulation_concern",
        "conflicts",
        "signals_for",
        "signals_against",
        "limitations",
    ],
}
class ProviderRefused(Exception):
    """The provider explicitly declined to produce an assessment."""


class GeminiResponse(BaseModel):
    """The only schema accepted from Gemini before applying verdict gates."""

    model_config = ConfigDict(extra="forbid")

    verdict: Literal["likely_real", "likely_manipulated", "insufficient"]
    confidence: float = Field(ge=0, le=1)
    deepfake_risk_code: Literal["low", "moderate", "high", "unknown"]
    manipulation_concern: bool
    conflicts: bool
    signals_for: list[str] = Field(max_length=6)
    signals_against: list[str] = Field(max_length=6)
    limitations: list[str] = Field(max_length=6)


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    media_base64: str = Field(min_length=4, max_length=MAX_BASE64_CHARS)
    digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    mime: str = Field(max_length=32)
    kind: str = Field(max_length=8)
    scope: str = Field(min_length=1, max_length=64)

    @field_validator("media_base64")
    @classmethod
    def validate_base64_characters(cls, value: str) -> str:
        if len(value) % 4 or not re.fullmatch(r"[A-Za-z0-9+/]*={0,2}", value):
            raise ValueError("invalid media encoding")
        return value

    @field_validator("kind")
    @classmethod
    def validate_kind(cls, value: str) -> str:
        if value not in MIMES_BY_KIND:
            raise ValueError("unsupported media kind")
        return value

    @field_validator("scope")
    @classmethod
    def validate_scope(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z_]+", value):
            raise ValueError("invalid analysis scope")
        return value


class BodySizeLimitMiddleware:
    """Buffers only a bounded JSON body before the ASGI application receives it."""

    def __init__(self, app: Any, limit: int = MAX_BODY_BYTES) -> None:
        self.app = app
        self.limit = limit

    async def __call__(self, scope: dict[str, Any], receive: Callable[..., Any], send: Callable[..., Any]) -> None:
        if scope["type"] != "http" or scope["path"] != "/analyze":
            await self.app(scope, receive, send)
            return
        address = str((scope.get("client") or ("unknown", 0))[0])[:64]
        if not preauth_rate_limiter.allow(address, f"preauth:{address}"):
            await _error_response(429, "request rate limit exceeded")(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        try:
            content_length = int(headers.get(b"content-length", b"0"))
        except ValueError:
            content_length = self.limit + 1
        if content_length > self.limit:
            await _error_response(413, "request body exceeds six MiB")(scope, receive, send)
            return

        chunks: list[bytes] = []
        total = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] != "http.request":
                continue
            chunk = message.get("body", b"")
            total += len(chunk)
            if total > self.limit:
                await _error_response(413, "request body exceeds six MiB")(scope, receive, send)
                return
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        body = b"".join(chunks)
        sent = False

        async def replay_receive() -> dict[str, Any]:
            nonlocal sent
            if sent:
                return {"type": "http.disconnect"}
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        await self.app(scope, replay_receive, send)


class SlidingWindowRateLimiter:
    """Instance-local limits keyed by address and validated token subject, never token."""

    def __init__(self, per_minute: int) -> None:
        self.per_minute = per_minute
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, address: str, subject: str) -> bool:
        now = monotonic()
        keys = (f"ip:{address[:64]}", f"subject:{subject}")
        with self._lock:
            for key in keys:
                events = self._events[key]
                while events and now - events[0] >= 60:
                    events.popleft()
                if len(events) >= self.per_minute:
                    return False
            for key in keys:
                self._events[key].append(now)
        return True


class DailyCallBudget:
    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.day = datetime.now(UTC).date()
        self.calls = 0
        self._lock = threading.Lock()

    def acquire(self) -> bool:
        today = datetime.now(UTC).date()
        with self._lock:
            if today != self.day:
                self.day, self.calls = today, 0
            if self.calls >= self.limit:
                return False
            self.calls += 1
        return True


class UnknownKidCache:
    """Short negative cache so repeated unknown JWT kids cannot refresh JWKS."""

    def __init__(self, ttl_seconds: int = 30, maximum: int = 512) -> None:
        self.ttl_seconds = ttl_seconds
        self.maximum = maximum
        self._values: dict[str, float] = {}
        self._lock = threading.Lock()

    def _prune(self, now: float) -> None:
        expired = [key for key, expires in self._values.items() if expires <= now]
        for key in expired:
            self._values.pop(key, None)
        while len(self._values) >= self.maximum:
            oldest = min(self._values, key=self._values.get)
            self._values.pop(oldest, None)

    def contains(self, kid: str) -> bool:
        now = monotonic()
        with self._lock:
            self._prune(now)
            return self._values.get(kid, 0) > now

    def add(self, kid: str) -> None:
        with self._lock:
            now = monotonic()
            self._prune(now)
            self._values[kid] = now + self.ttl_seconds


def _env_positive_int(name: str, default: int, maximum: int) -> int:
    try:
        return min(maximum, max(1, int(os.getenv(name, str(default)))))
    except ValueError:
        return default


jwks_client = jwt.PyJWKClient(JWKS_URL, cache_keys=True, lifespan=300, timeout=3)
unknown_kids = UnknownKidCache()
preauth_rate_limiter = SlidingWindowRateLimiter(
    _env_positive_int("WORKER_PREAUTH_RATE_LIMIT_PER_MINUTE", 60, 240)
)
rate_limiter = SlidingWindowRateLimiter(_env_positive_int("WORKER_RATE_LIMIT_PER_MINUTE", 12, 120))
daily_budget = DailyCallBudget(_env_positive_int("WORKER_DAILY_CALL_LIMIT", 200, 10_000))
analysis_semaphore = asyncio.Semaphore(_env_positive_int("WORKER_CONCURRENCY", 2, 8))


def _error_response(status: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"detail": message},
        headers={"Cache-Control": "no-store"},
    )


def _http_error(status: int, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail=message, headers={"Cache-Control": "no-store"})


def verify_vercel_oidc(
    token: str, client: Any | None = None, decode_func: Callable[..., dict[str, Any]] = jwt.decode
) -> dict[str, Any]:
    """Validate a Vercel production OIDC token using the fixed project JWKS."""
    if not token or len(token) > 16_384:
        raise _http_error(401, "valid bearer authentication is required")
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
            raise jwt.InvalidTokenError("unsupported token header")
    except jwt.PyJWTError:
        raise _http_error(401, "valid bearer authentication is required") from None
    kid = header["kid"][:256]
    if unknown_kids.contains(kid):
        raise _http_error(401, "valid bearer authentication is required")
    try:
        signing_key = (client or jwks_client).get_signing_key_from_jwt(token)
    except jwt.PyJWKClientError:
        unknown_kids.add(kid)
        raise _http_error(401, "valid bearer authentication is required") from None
    try:
        claims = decode_func(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=OIDC_AUDIENCE,
            issuer=OIDC_ISSUER,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
    except jwt.PyJWTError:
        raise _http_error(401, "valid bearer authentication is required") from None
    if claims.get("sub") != OIDC_SUBJECT:
        raise _http_error(403, "production project authorization is required")
    if (
        claims.get("owner") != "soldioms-projects"
        or claims.get("project") != "sanad"
        or claims.get("environment") != "production"
    ):
        raise _http_error(403, "production project authorization is required")
    return claims


def extract_bearer_token(request: Request) -> str:
    authorization = request.headers.get("authorization", "")
    scheme, separator, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not separator or not token or token.strip() != token:
        raise _http_error(401, "valid bearer authentication is required")
    return token


def decode_and_validate_media(payload: AnalyzeRequest) -> bytes:
    if payload.mime not in MIMES_BY_KIND[payload.kind]:
        raise _http_error(415, "media kind and MIME type do not match")
    try:
        media = base64.b64decode(payload.media_base64, validate=True)
    except (binascii.Error, ValueError):
        raise _http_error(422, "media encoding is invalid") from None
    if not media or len(media) > MAX_MEDIA_BYTES:
        raise _http_error(413, "decoded media exceeds six MiB")
    actual = hashlib.sha256(media).hexdigest()
    if not hmac.compare_digest(actual, payload.digest):
        raise _http_error(422, "media digest does not match")
    return media


def _run(command: list[str], timeout: int) -> tuple[int, str, str]:
    try:
        completed = subprocess.run(
            command, stdin=subprocess.DEVNULL, capture_output=True, text=True,
            timeout=timeout, check=False, cwd="/tmp",
        )
        return completed.returncode, completed.stdout[:32_768], completed.stderr[:32_768]
    except (subprocess.TimeoutExpired, OSError):
        return 1, "", "tool unavailable or timed out"


def _run_bytes(command: list[str], timeout: int, maximum_output: int) -> tuple[int, bytes]:
    """Run a command whose output size is fixed by its ffmpeg PCM parameters."""
    try:
        completed = subprocess.run(
            command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=timeout, check=False, cwd="/tmp",
        )
        if len(completed.stdout) > maximum_output:
            return 1, b""
        return completed.returncode, completed.stdout
    except (subprocess.TimeoutExpired, OSError):
        return 1, b""


def _spectral_centroid_hz(pcm: bytes, sample_rate: int = 8_000) -> float | None:
    """Calculate a small, bounded magnitude-spectrum centroid from mono PCM."""
    sample_count = min(1024, len(pcm) // 2)
    if sample_count < 128:
        return None
    samples = struct.unpack(f"<{sample_count}h", pcm[:sample_count * 2])
    average = sum(samples) / sample_count
    centered = [sample - average for sample in samples]
    weighted_frequency = 0.0
    total_magnitude = 0.0
    for bin_index in range(1, sample_count // 4):
        real = imag = 0.0
        for sample_index, sample in enumerate(centered):
            angle = 2 * math.pi * bin_index * sample_index / sample_count
            real += sample * math.cos(angle)
            imag -= sample * math.sin(angle)
        magnitude = math.hypot(real, imag)
        weighted_frequency += (bin_index * sample_rate / sample_count) * magnitude
        total_magnitude += magnitude
    return round(weighted_frequency / total_magnitude, 1) if total_magnitude else None


def _ffprobe(path: Path) -> dict[str, Any] | None:
    command = [
        "ffprobe", "-v", "error", "-show_entries",
        "format=format_name,duration:format_tags=encoder,software:stream=index,codec_type,codec_name,width,height,sample_rate,channels",
        "-of", "json", str(path),
    ]
    code, stdout, _ = _run(command, timeout=8)
    if code:
        return None
    try:
        data = json.loads(stdout)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def has_editing_marker(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in EDITING_MARKERS)


def inspect_image(media: bytes, mime: str) -> tuple[dict[str, Any], list[str], bool]:
    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
    try:
        from io import BytesIO

        with Image.open(BytesIO(media)) as image:
            declared_format = "JPEG" if mime == "image/jpeg" else "PNG"
            if image.format != declared_format:
                raise ValueError("format mismatch")
            image.verify()
        with Image.open(BytesIO(media)) as image:
            width, height = image.size
            info = image.getexif()
            software = str(info.get(305, "")).strip()
            facts = {"format": declared_format, "width": width, "height": height, "has_exif": bool(info)}
            signals = [f"Decoded {declared_format} image dimensions: {width}x{height}."]
            if software:
                facts["editing_software_metadata"] = True
                signals.append("Image metadata includes software-editing provenance.")
            return facts, signals, has_editing_marker(software)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise _http_error(415, "media bytes do not match the declared image format") from None


def _duration(probe: dict[str, Any]) -> float:
    try:
        return max(0.0, min(MAX_VIDEO_DURATION_SECONDS, float(probe.get("format", {}).get("duration", 0))))
    except (TypeError, ValueError):
        return 0.0


def inspect_video(media: bytes, suffix: str) -> tuple[dict[str, Any], list[str], bool, list[tuple[float, bytes]]]:
    with tempfile.TemporaryDirectory(prefix="sanad-media-") as directory:
        source = Path(directory, f"source{suffix}")
        source.write_bytes(media)
        probe = _ffprobe(source)
        streams = probe.get("streams", []) if probe else []
        video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
        if not video_stream:
            raise _http_error(415, "media bytes do not contain a decodable video stream")
        try:
            width = int(video_stream.get("width") or 0)
            height = int(video_stream.get("height") or 0)
        except (TypeError, ValueError):
            width = height = 0
        if (
            width <= 0
            or height <= 0
            or width > MAX_VIDEO_DIMENSION
            or height > MAX_VIDEO_DIMENSION
            or width * height > MAX_VIDEO_PIXELS
            or max(width / height, height / width) > MAX_VIDEO_ASPECT_RATIO
        ):
            raise _http_error(415, "video dimensions exceed the bounded decoder limits")
        try:
            raw_duration = float(probe.get("format", {}).get("duration", 0))
        except (TypeError, ValueError):
            raw_duration = 0
        if raw_duration <= 0 or raw_duration > MAX_VIDEO_DURATION_SECONDS:
            raise _http_error(415, "video duration exceeds the bounded analysis limit")
        duration = _duration(probe)
        timestamps = sorted({0.0, round(duration / 2, 3), round(max(0, duration - 0.25), 3)})
        frames: list[tuple[float, bytes]] = []
        for index, timestamp in enumerate(timestamps[:3]):
            target = Path(directory, f"frame-{index}.jpg")
            command = [
                "ffmpeg", "-nostdin", "-v", "error", "-threads", "1",
                "-max_alloc", str(64 * 1024 * 1024), "-ss", str(timestamp),
                "-i", str(source), "-frames:v", "1", "-vf",
                "scale=w='min(768,iw)':h='min(768,ih)':force_original_aspect_ratio=decrease",
                "-q:v", "4", "-fs", str(MAX_FRAME_BYTES), "-y", str(target),
            ]
            code, _, _ = _run(command, timeout=10)
            if not code and target.exists() and 0 < target.stat().st_size <= MAX_FRAME_BYTES:
                frames.append((timestamp, target.read_bytes()))
        format_tags = probe.get("format", {}).get("tags", {}) or {}
        encoder = str(format_tags.get("encoder") or format_tags.get("software") or "").strip()
        facts = {
            "container": str(probe.get("format", {}).get("format_name", ""))[:100],
            "duration_seconds": duration,
            "codec": str(video_stream.get("codec_name", ""))[:50],
            "width": width,
            "height": height,
            "sampled_timestamps_seconds": [timestamp for timestamp, _ in frames],
        }
        signals = [
            f"Decoded video stream: {facts['codec']} {facts['width']}x{facts['height']}.",
            f"Representative frames decoded at {len(frames)} bounded timestamp(s).",
        ]
        editing_signal = has_editing_marker(encoder)
        if encoder:
            facts["editing_software_metadata"] = True
            signals.append("Container metadata includes encoder or software provenance.")
        return facts, signals, editing_signal, frames


def inspect_audio(media: bytes, suffix: str) -> tuple[dict[str, Any], list[str], bool]:
    with tempfile.TemporaryDirectory(prefix="sanad-media-") as directory:
        source = Path(directory, f"source{suffix}")
        source.write_bytes(media)
        probe = _ffprobe(source)
        streams = probe.get("streams", []) if probe else []
        audio_stream = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
        if not audio_stream:
            raise _http_error(415, "media bytes do not contain a decodable audio stream")
        command = [
            "ffmpeg", "-nostdin", "-v", "info", "-threads", "1", "-i", str(source), "-t",
            str(MAX_AUDIO_ANALYSIS_SECONDS), "-af",
            "volumedetect,silencedetect=n=-50dB:d=0.5,astats=metadata=1:reset=1",
            "-f", "null", "-",
        ]
        _, _, diagnostics = _run(command, timeout=15)
        peak = re.search(r"max_volume:\s*(-?[\d.]+)\s*dB", diagnostics)
        silence = [float(value) for value in re.findall(r"silence_duration:\s*([\d.]+)", diagnostics)]
        zcr = re.search(r"Zero crossings rate:\s*([\d.]+)", diagnostics)
        duration = _duration(probe)
        facts = {
            "container": str(probe.get("format", {}).get("format_name", ""))[:100],
            "duration_seconds": duration,
            "codec": str(audio_stream.get("codec_name", ""))[:50],
            "sample_rate": audio_stream.get("sample_rate"),
            "channels": audio_stream.get("channels"),
            "analysis_window_seconds": min(duration, MAX_AUDIO_ANALYSIS_SECONDS),
            "silence_durations_seconds": silence[:8],
        }
        if peak:
            facts["peak_dbfs"] = float(peak.group(1))
            facts["near_full_scale_clipping_indicator"] = float(peak.group(1)) >= -0.1
        if zcr:
            facts["zero_crossing_rate"] = float(zcr.group(1))
        pcm_code, pcm = _run_bytes(
            [
                "ffmpeg", "-nostdin", "-v", "error", "-threads", "1", "-i", str(source),
                "-t", str(min(10, max(1, duration))), "-ac", "1", "-ar", "8000",
                "-f", "s16le", "-",
            ],
            timeout=12,
            maximum_output=160_000,
        )
        if not pcm_code:
            centroid = _spectral_centroid_hz(pcm)
            if centroid is not None:
                facts["spectral_centroid_hz"] = centroid
        encoder = str((probe.get("format", {}).get("tags", {}) or {}).get("encoder", "")).strip()
        signals = [
            f"Decoded audio stream: {facts['codec']} at {facts['sample_rate']} Hz.",
            f"Analyzed up to {facts['analysis_window_seconds']:.3f} seconds for peak, silence, and spectral facts.",
        ]
        editing_signal = has_editing_marker(encoder)
        if encoder:
            facts["editing_software_metadata"] = True
            signals.append("Container metadata includes encoder provenance.")
        return facts, signals, editing_signal


def run_deterministic_checks(payload: AnalyzeRequest, media: bytes) -> tuple[dict[str, Any], list[str], bool, dict[str, Any], list[tuple[float, bytes]]]:
    suffix = MIMES_BY_KIND[payload.kind][payload.mime]
    if payload.kind == "image":
        facts, signals, concern = inspect_image(media, payload.mime)
        return facts, signals, concern, {"mode": "direct-image-bytes"}, []
    if payload.kind == "video":
        facts, signals, concern, frames = inspect_video(media, suffix)
        return facts, signals, concern, {
            "mode": "representative-frames", "requested_timestamps_seconds": [0, "midpoint", "near_end"],
            "decoded_frame_count": len(frames), "timestamps_seconds": [timestamp for timestamp, _ in frames],
        }, frames
    facts, signals, concern = inspect_audio(media, suffix)
    return facts, signals, concern, {
        "mode": "bounded-audio-facts", "max_analysis_seconds": MAX_AUDIO_ANALYSIS_SECONDS,
        "duration_seconds": facts["duration_seconds"],
    }, []


def _clean_strings(value: Any) -> list[str]:
    return [
        item.strip()[:300] for item in (value if isinstance(value, list) else [])
        if isinstance(item, str) and item.strip()
    ][:6]


def _gemini_contents(payload: AnalyzeRequest, media: bytes, facts: dict[str, Any], frames: list[tuple[float, bytes]]) -> list[Any]:
    instruction = (
        "Assess only potential media-manipulation indicators. Do not identify people or voices, "
        "and do not make a definitive authenticity claim. Return JSON matching the supplied schema only. "
        "Set manipulation_concern only when your visual/audio assessment has a concrete concern. "
        "Set conflicts when the supplied deterministic facts materially conflict with your assessment. "
        f"Media kind: {payload.kind}; declared MIME: {payload.mime}; scope: {payload.scope}. "
        f"Deterministic facts: {json.dumps(facts, sort_keys=True)}"
    )
    contents: list[Any] = [instruction, types.Part.from_bytes(data=media, mime_type=payload.mime)]
    for timestamp, frame in frames:
        contents.extend([
            f"Representative decoded video frame timestamp seconds: {timestamp:.3f}",
            types.Part.from_bytes(data=frame, mime_type="image/jpeg"),
        ])
    return contents


def ask_gemini(payload: AnalyzeRequest, media: bytes, facts: dict[str, Any], frames: list[tuple[float, bytes]], client: Any | None = None) -> dict[str, Any]:
    gemini = client or genai.Client(
        api_key=os.getenv("GEMINI_API_KEY"),
        http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT_MS),
    )
    response = gemini.models.generate_content(
        model=GEMINI_MODEL,
        contents=_gemini_contents(payload, media, facts, frames),
        config=types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
            response_schema=PROVIDER_RESPONSE_SCHEMA,
        ),
    )
    try:
        response_text = response.text
    except (AttributeError, ValueError):
        response_text = None
    if not response_text:
        feedback = getattr(response, "prompt_feedback", None)
        candidates = getattr(response, "candidates", None) or []
        finish_reasons = [str(getattr(candidate, "finish_reason", "")).upper() for candidate in candidates]
        if getattr(feedback, "block_reason", None) or any(
            reason in {"SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT"}
            for reason in finish_reasons
        ):
            raise ProviderRefused()
        raise ValueError("empty provider response")
    return GeminiResponse.model_validate_json(response_text).model_dump()


def insufficient_result(payload: AnalyzeRequest, media_bytes: int, status: str, limitation: str, sampling: dict[str, Any]) -> dict[str, Any]:
    return {
        "verdict": "insufficient",
        "verdict_label_en": "Insufficient evidence",
        "confidence": None,
        "deepfake_risk_code": "unknown",
        "deepfake_risk": ARABIC_RISK["unknown"],
        "signals_for": [],
        "signals_against": [],
        "limitations": [limitation],
        "provider": "gemini",
        "provider_status": status,
        "checked_at": datetime.now(UTC).isoformat(),
        "analysis_scope": payload.scope,
        "bytes_analyzed": media_bytes,
        "model_version": GEMINI_MODEL,
        "worker_version": WORKER_VERSION,
        "sampling": sampling,
    }


def build_result(
    payload: AnalyzeRequest, media_bytes: int, deterministic_signals: list[str],
    deterministic_concern: bool, sampling: dict[str, Any], model: dict[str, Any],
) -> dict[str, Any]:
    candidate = model.get("verdict")
    model_concern = model.get("manipulation_concern") is True
    conflicts = model.get("conflicts") is True
    try:
        model_confidence = min(1.0, max(0.0, float(model.get("confidence"))))
    except (TypeError, ValueError):
        model_confidence = 0.0
    model_support = bool(_clean_strings(model.get("signals_for")))
    model_against = bool(_clean_strings(model.get("signals_against")))
    support = bool(deterministic_signals)
    direct_complete = (
        payload.scope in DIRECT_SCOPES
        and media_bytes > 0
        and support
        and not conflicts
        and not deterministic_concern
    )
    if (
        candidate == "likely_manipulated"
        and model_concern
        and model_against
        and deterministic_concern
        and model_confidence >= 0.75
    ):
        verdict = "likely_manipulated"
    elif (
        candidate == "likely_real"
        and direct_complete
        and model_support
        and not model_concern
        and model_confidence >= 0.75
    ):
        verdict = "likely_real"
    else:
        verdict = "insufficient"
    risk = model.get("deepfake_risk_code") if model.get("deepfake_risk_code") in ARABIC_RISK else "unknown"
    confidence = model_confidence if verdict != "insufficient" else None
    limitations = _clean_strings(model.get("limitations"))
    if verdict == "insufficient":
        limitations = limitations + ["Evidence did not meet the conservative verdict gate."] if limitations else [
            "Evidence did not meet the conservative verdict gate."
        ]
        risk = "unknown"
    return {
        "verdict": verdict,
        "verdict_label_en": (
            "No clear manipulation indicators detected"
            if verdict == "likely_real"
            else "Likely manipulated"
            if verdict == "likely_manipulated"
            else "Insufficient evidence"
        ),
        "confidence": confidence,
        "deepfake_risk_code": risk,
        "deepfake_risk": ARABIC_RISK[risk],
        "signals_for": _clean_strings(model.get("signals_for")) + deterministic_signals[:3],
        "signals_against": _clean_strings(model.get("signals_against")),
        "limitations": limitations[:8],
        "provider": "gemini",
        "provider_status": "completed",
        "checked_at": datetime.now(UTC).isoformat(),
        "analysis_scope": payload.scope,
        "bytes_analyzed": media_bytes,
        "model_version": GEMINI_MODEL,
        "worker_version": WORKER_VERSION,
        "sampling": sampling,
    }


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(BodySizeLimitMiddleware)


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, __: RequestValidationError) -> JSONResponse:
    return _error_response(422, "request payload is invalid")


@app.middleware("http")
async def no_store(_: Request, call_next: Callable[..., Any]) -> Response:
    response = await call_next(_)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "ready": bool(os.getenv("GEMINI_API_KEY")),
        "provider": "gemini",
        "model_version": GEMINI_MODEL,
        "worker_version": WORKER_VERSION,
        "authentication": "vercel_oidc_production",
        "analysis_scope": sorted(DIRECT_SCOPES),
        "max_media_bytes": MAX_MEDIA_BYTES,
    }


@app.post("/analyze")
async def analyze(payload: AnalyzeRequest, request: Request) -> dict[str, Any]:
    client_address = request.client.host if request.client else "unknown"
    token = extract_bearer_token(request)
    claims = await asyncio.to_thread(verify_vercel_oidc, token)
    if not rate_limiter.allow(client_address, claims["sub"]):
        raise _http_error(429, "request rate limit exceeded")
    media = decode_and_validate_media(payload)
    try:
        await asyncio.wait_for(analysis_semaphore.acquire(), timeout=0.1)
    except TimeoutError:
        raise _http_error(503, "analysis capacity is currently unavailable") from None
    if not daily_budget.acquire():
        analysis_semaphore.release()
        raise _http_error(429, "daily analysis limit exceeded")
    try:
        facts, signals, deterministic_concern, sampling, frames = await asyncio.to_thread(
            run_deterministic_checks, payload, media
        )
        try:
            model = await asyncio.wait_for(
                asyncio.to_thread(ask_gemini, payload, media, facts, frames),
                timeout=GEMINI_DEADLINE_SECONDS,
            )
        except TimeoutError:
            return insufficient_result(
                payload, len(media), "provider_timeout",
                "The model provider timed out before returning usable analysis.", sampling,
            )
        except ProviderRefused:
            return insufficient_result(
                payload, len(media), "provider_refused",
                "The model provider declined this bounded analysis.", sampling,
            )
        except Exception:
            return insufficient_result(
                payload, len(media), "provider_failed",
                "The model provider did not return usable structured analysis.", sampling,
            )
        return build_result(payload, len(media), signals, deterministic_concern, sampling, model)
    finally:
        analysis_semaphore.release()
