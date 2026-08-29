#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic SANAD event and signal products for read-only consumers."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit


OUT = Path(os.environ.get("SANAD_DAILY", "daily"))
SCHEMA_VERSION = "1.0"
EVENT_MAX_HOURS = 7 * 24
WATCH_MAX_HOURS = 72
TENSION_MAX_HOURS = 6
PAPER_MAX_HOURS = 21 * 24
REPO_MAX_HOURS = 45 * 24
RISK_THRESHOLD = 60

_AR_DIACRITICS = re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]")
_NON_WORD = re.compile(r"[^\w\u0600-\u06ff]+", re.UNICODE)
_STOP = {
    "the", "a", "an", "of", "to", "in", "on", "for", "and", "or", "from",
    "عن", "في", "من", "إلى", "الى", "على", "و", "أو", "او", "بعد", "قبل",
    "قال", "تقول", "يقول", "أعلن", "اعلن", "أعلنت", "اعلنت",
}
_DENIAL = {
    "ينفي", "نفت", "نفى", "تنفي", "نفي", "ينفون", "لا", "صحة", "غير", "صحيح",
    "denies", "denied", "deny", "false", "not", "no",
}
_DENIAL_PHRASES = ("لا صحة", "غير صحيح", "ينفي", "تنفي", "نفت", "نفى", "denies", "denied", "false")

_COUNTRIES = {
    "kw": ("Kuwait", ("الكويت", "kuwait")),
    "sa": ("Saudi Arabia", ("السعودية", "saudi")),
    "ae": ("United Arab Emirates", ("الإمارات", "الامارات", "uae", "united arab emirates")),
    "qa": ("Qatar", ("قطر", "qatar")),
    "bh": ("Bahrain", ("البحرين", "bahrain")),
    "om": ("Oman", ("عمان", "oman")),
    "iq": ("Iraq", ("العراق", "iraq")),
    "ir": ("Iran", ("إيران", "ايران", "iran")),
    "ps": ("Palestine", ("فلسطين", "غزة", "غزه", "palestine", "gaza")),
    "il": ("Israel", ("إسرائيل", "اسرائيل", "israel")),
    "lb": ("Lebanon", ("لبنان", "lebanon")),
    "sy": ("Syria", ("سوريا", "syria")),
    "jo": ("Jordan", ("الأردن", "الاردن", "jordan")),
    "eg": ("Egypt", ("مصر", "egypt")),
    "ye": ("Yemen", ("اليمن", "yemen")),
    "us": ("United States", ("الولايات المتحدة", "أمريكا", "امريكا", "united states", "usa")),
}

_TOPICS = {
    "artificial-intelligence": ("ذكاء اصطناعي", "ai", "artificial intelligence", "llm", "model", "نموذج"),
    "security": ("أمن", "امن", "security", "cyber", "هجوم", "attack"),
    "conflict": ("حرب", "قصف", "صاروخ", "عسكري", "اشتباك", "war", "missile", "military"),
    "diplomacy": ("دبلوماس", "مفاوض", "اتفاق", "وزارة الخارجية", "diplom", "negotiat", "agreement"),
    "economy": ("اقتصاد", "بنك", "سوق", "نفط", "مال", "econom", "bank", "market", "oil"),
    "health": ("صحة", "مستشفى", "طبي", "health", "hospital", "medical"),
    "climate": ("طقس", "مناخ", "حرائق", "زلزال", "weather", "climate", "fire", "earthquake"),
    "technology": ("تقنية", "تكنولوجيا", "برمج", "technology", "software", "github"),
}

_SECTORS = {
    "government": ("وزارة", "حكومة", "رسمي", "government", "ministry", "official"),
    "finance": ("بنك", "مصرف", "سوق", "مال", "bank", "finance", "market"),
    "health": ("صحة", "مستشفى", "طبي", "health", "hospital", "medical"),
    "energy": ("نفط", "غاز", "طاقة", "oil", "gas", "energy"),
    "defense": ("دفاع", "عسكري", "جيش", "صاروخ", "defense", "military", "missile"),
    "technology": ("ذكاء اصطناعي", "تقنية", "برمج", "ai", "technology", "software"),
    "transport": ("طيران", "ميناء", "طريق", "flight", "airport", "port", "road"),
}

_AI_PAPER_TOPICS = {
    "agents": ("agent", "tool use", "multi-agent", "وكيل"),
    "language-models": ("language model", "llm", "reasoning", "transformer"),
    "computer-vision": ("vision", "image", "video", "3d", "gaussian"),
    "robotics": ("robot", "embodied", "manipulation"),
    "retrieval": ("retrieval", "rag", "search"),
}

_SIGNAL_FIELDS = (
    "id", "type", "title", "title_en", "summary", "observed_at", "valid_until",
    "observed_facts", "assessment", "inference", "uncertainty", "confidence",
    "severity", "countries", "sectors", "topics", "evidence", "contradictions",
    "event_ids", "created_at", "updated_at",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="minutes")


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.fromisoformat(text[:10] + "T00:00:00+00:00")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _fresh(value: Any, now: datetime, max_hours: int) -> bool:
    parsed = _parse_ts(value)
    if parsed is None:
        return False
    age = (now - parsed).total_seconds() / 3600
    return -1 <= age <= max_hours


def _hash(prefix: str, value: str) -> str:
    return prefix + hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _normalize_text(value: Any) -> str:
    text = _AR_DIACRITICS.sub("", str(value or "").lower())
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ى", "ي")
    return " ".join(x for x in _NON_WORD.sub(" ", text).split() if x and x not in _STOP)


def _tokens(value: Any, remove_denial: bool = False) -> set[str]:
    words = set(_normalize_text(value).split())
    if remove_denial:
        words -= _DENIAL
    return {word for word in words if len(word) > 1}


def _canonical_url(value: Any) -> str:
    text = str(value or "").strip()
    if not text.startswith(("http://", "https://")):
        return ""
    parts = urlsplit(text)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), "", ""))


def _has_denial(value: Any) -> bool:
    text = _normalize_text(value)
    return any(_normalize_text(phrase) in text for phrase in _DENIAL_PHRASES)


def _similarity(left: Any, right: Any, remove_denial: bool = False) -> tuple[float, int]:
    a, b = _tokens(left, remove_denial), _tokens(right, remove_denial)
    if not a or not b:
        return 0.0, 0
    shared = len(a & b)
    return shared / len(a | b), shared


def _classify(text: str, mapping: dict[str, tuple[str, ...]]) -> list[str]:
    normalized = _normalize_text(text)
    return sorted(
        key for key, aliases in mapping.items()
        if any(_normalize_text(alias) in normalized for alias in aliases)
    )


def _country_ids(text: str, explicit: list[str] | None = None) -> list[str]:
    found = set(explicit or [])
    normalized = _normalize_text(text)
    for code, (_, aliases) in _COUNTRIES.items():
        if any(_normalize_text(alias) in normalized for alias in aliases):
            found.add(code)
    return sorted(found)


def _severity(text: str) -> str:
    normalized = _normalize_text(text)
    if any(word in normalized for word in ("اخلاء فوري", "هجوم واسع", "mass casualty", "evacuation")):
        return "high"
    if any(word in normalized for word in ("قصف", "صاروخ", "انفجار", "زلزال", "هجوم", "missile", "explosion")):
        return "medium"
    return "info"


def _evidence(
    title: Any,
    title_en: Any,
    source: Any,
    grade: Any,
    url: Any,
    observed_at: Any,
    dataset: str,
) -> dict[str, Any]:
    canonical_url = _canonical_url(url)
    stable = canonical_url or (_normalize_text(title) + "|" + _normalize_text(source))
    return {
        "id": _hash("ev_", stable),
        "url": str(url or ""),
        "source_name": str(source or ""),
        "source_grade": str(grade or ""),
        "observed_at": str(observed_at or ""),
        "title": str(title or ""),
        "title_en": str(title_en or ""),
        "dataset": dataset,
    }


def _observation(
    title: Any,
    title_en: Any,
    source: Any,
    grade: Any,
    url: Any,
    observed_at: Any,
    dataset: str,
    *,
    countries: list[str] | None = None,
    topics: list[str] | None = None,
) -> dict[str, Any] | None:
    title = str(title or "").strip()
    if not title:
        return None
    blob = title + " " + str(title_en or "")
    return {
        "title": title,
        "title_en": str(title_en or ""),
        "countries": _country_ids(blob, countries),
        "topics": sorted(set(topics or []) | set(_classify(blob, _TOPICS))),
        "sectors": _classify(blob, _SECTORS),
        "evidence": _evidence(title, title_en, source, grade, url, observed_at, dataset),
    }


def _collect_observations(inputs: dict[str, dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    news = inputs.get("news") or {}
    for category, items in (news.get("cats") or {}).items():
        for item in items if isinstance(items, list) else []:
            at = item.get("at") or news.get("updated")
            if not _fresh(at, now, EVENT_MAX_HOURS):
                continue
            obs = _observation(
                item.get("head"), item.get("he"), item.get("src"), item.get("grade"),
                item.get("link"), at, "news", topics=[str(category)],
            )
            if obs:
                rows.append(obs)

    official = inputs.get("official") or {}
    for item in official.get("src") or []:
        at = item.get("cap") or official.get("updated")
        if not _fresh(at, now, EVENT_MAX_HOURS):
            continue
        obs = _observation(
            item.get("p") or item.get("h"), "", item.get("e"), item.get("grade"),
            item.get("u"), at, "official",
        )
        if obs:
            rows.append(obs)

    osint = inputs.get("osint") or {}
    for watch in osint.get("watches") or []:
        watch_topics = [str(x) for x in (watch.get("topic"), watch.get("term")) if x]
        for item in watch.get("hits") or []:
            at = item.get("at") or osint.get("updated")
            if not _fresh(at, now, EVENT_MAX_HOURS):
                continue
            obs = _observation(
                item.get("head"), item.get("he"), item.get("src"), item.get("grade"),
                item.get("link"), at, "osint", topics=watch_topics,
            )
            if obs:
                rows.append(obs)

    world_map = inputs.get("map") or {}
    for country in world_map.get("countries") or []:
        code = str(country.get("id") or "")
        for item in country.get("stories") or []:
            at = item.get("at") or world_map.get("updated")
            if not _fresh(at, now, EVENT_MAX_HOURS):
                continue
            obs = _observation(
                item.get("head"), item.get("he"), item.get("src"), item.get("grade"),
                item.get("link"), at, "map", countries=[code] if code else None,
            )
            if obs:
                rows.append(obs)

    deduped: dict[str, dict[str, Any]] = {}
    for row in rows:
        ev = row["evidence"]
        key = ev["id"]
        current = deduped.get(key)
        if current is None:
            deduped[key] = row
            continue
        current["countries"] = sorted(set(current["countries"]) | set(row["countries"]))
        current["topics"] = sorted(set(current["topics"]) | set(row["topics"]))
        current["sectors"] = sorted(set(current["sectors"]) | set(row["sectors"]))
        if not current["evidence"]["source_grade"] and ev["source_grade"]:
            current["evidence"]["source_grade"] = ev["source_grade"]
    return sorted(deduped.values(), key=lambda row: row["evidence"]["id"])


def _related(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_url = _canonical_url(left["evidence"].get("url"))
    right_url = _canonical_url(right["evidence"].get("url"))
    if left_url and left_url == right_url:
        return True
    left_title, right_title = left["title"], right["title"]
    if _normalize_text(left_title) == _normalize_text(right_title):
        return True
    score, shared = _similarity(left_title, right_title)
    if score >= 0.78 and shared >= 3:
        return True
    if _has_denial(left_title) != _has_denial(right_title):
        score, shared = _similarity(left_title, right_title, remove_denial=True)
        return score >= 0.5 and shared >= 2
    return False


def cluster_observations(observations: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Conservatively cluster observations; input order does not affect output."""
    rows = sorted(observations, key=lambda row: row["evidence"]["id"])
    parent = list(range(len(rows)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        a, b = find(left), find(right)
        if a != b:
            parent[max(a, b)] = min(a, b)

    for left in range(len(rows)):
        for right in range(left + 1, len(rows)):
            if _related(rows[left], rows[right]):
                union(left, right)

    groups: dict[int, list[dict[str, Any]]] = {}
    for index, row in enumerate(rows):
        groups.setdefault(find(index), []).append(row)
    return sorted(groups.values(), key=lambda group: group[0]["evidence"]["id"])


def _contradictions(group: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for left_index, left in enumerate(group):
        for right in group[left_index + 1:]:
            if _has_denial(left["title"]) == _has_denial(right["title"]):
                continue
            score, shared = _similarity(left["title"], right["title"], remove_denial=True)
            if score < 0.5 or shared < 2:
                continue
            pair = sorted((left["evidence"]["id"], right["evidence"]["id"]))
            out.append({
                "id": _hash("con_", "|".join(pair)),
                "type": "explicit-denial",
                "summary": "One attributable headline explicitly denies a substantially overlapping claim.",
                "evidence_ids": pair,
            })
    return sorted(out, key=lambda row: row["id"])


def _content_fingerprint(record: dict[str, Any]) -> str:
    clean = {key: value for key, value in record.items() if key not in ("created_at", "updated_at")}
    return json.dumps(clean, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _carry_times(record: dict[str, Any], previous: dict[str, Any] | None, now: str) -> dict[str, Any]:
    record["created_at"] = (previous or {}).get("created_at") or now
    if previous and _content_fingerprint(previous) == _content_fingerprint(record):
        record["updated_at"] = previous.get("updated_at") or now
    else:
        record["updated_at"] = now
    return record


def _assign_event_ids(
    groups: list[list[dict[str, Any]]],
    previous_events: list[dict[str, Any]],
) -> dict[int, str]:
    """Reuse a prior ID when any retained evidence still identifies the cluster."""
    previous = []
    for event in previous_events:
        evidence_ids = {row.get("id") for row in event.get("evidence") or [] if row.get("id")}
        if event.get("id") and evidence_ids:
            previous.append((event, evidence_ids))
    assigned: dict[int, str] = {}
    used_previous: set[str] = set()
    candidates = []
    for index, group in enumerate(groups):
        current_ids = {row["evidence"]["id"] for row in group}
        for event, evidence_ids in previous:
            overlap = len(current_ids & evidence_ids)
            if overlap:
                candidates.append((
                    -overlap,
                    str(event.get("created_at") or ""),
                    str(event["id"]),
                    index,
                ))
    for _, _, event_id, index in sorted(candidates):
        if index not in assigned and event_id not in used_previous:
            assigned[index] = event_id
            used_previous.add(event_id)
    for index, group in enumerate(groups):
        if index not in assigned:
            anchor = min(row["evidence"]["id"] for row in group)
            assigned[index] = _hash("evt_", anchor)
    return assigned


def _confidence(evidence: list[dict[str, Any]]) -> float:
    grades = [row.get("source_grade") for row in evidence]
    base = 0.9 if "صحيح" in grades else (0.72 if "حسن" in grades else 0.45)
    sources = {row.get("source_name") for row in evidence if row.get("source_name")}
    if len(sources) >= 2:
        base += 0.08
    return round(min(0.95, base), 2)


def build_events(
    inputs: dict[str, dict[str, Any]],
    *,
    now: datetime | None = None,
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now_dt = now or _now()
    now_iso = _iso(now_dt)
    previous_by_id = {row["id"]: row for row in (previous or {}).get("events", []) if row.get("id")}
    groups = cluster_observations(_collect_observations(inputs, now_dt))
    assigned_ids = _assign_event_ids(groups, list(previous_by_id.values()))
    events = []
    for group_index, group in enumerate(groups):
        evidence = sorted((row["evidence"] for row in group), key=lambda row: row["id"])
        titles = sorted({row["title"] for row in group})
        facts = sorted({
            f"{row['evidence']['source_name'] or 'Attributed source'} published: {row['title']}"
            for row in group
        })
        countries = sorted({value for row in group for value in row["countries"]})
        topics = sorted({_normalize_text(value).replace(" ", "-") for row in group for value in row["topics"] if value})
        sectors = sorted({value for row in group for value in row["sectors"]})
        contradictions = _contradictions(group)
        event_id = assigned_ids[group_index]
        sources = {row["source_name"] for row in evidence if row["source_name"]}
        graded = sum(1 for row in evidence if row["source_grade"] in ("صحيح", "حسن"))
        assessment = f"{len(evidence)} attributable observation(s); {graded} carry an existing SANAD source grade."
        inference = ""
        if len(sources) >= 2:
            inference = "Multiple named sources appear to describe the same event; linkage is based on URL or conservative headline overlap."
        uncertainty = "Headline-level deterministic clustering only; evidence links should be read before operational use."
        if contradictions:
            uncertainty = "Attributable headlines explicitly conflict; SANAD does not resolve the underlying claim in this product."
        event = {
            "id": event_id,
            "type": "observed-event",
            "title": titles[0],
            "title_en": next((row["title_en"] for row in group if row["title_en"]), ""),
            "observed_facts": facts,
            "sanad_assessment": assessment,
            "inference": inference,
            "uncertainty": uncertainty,
            "confidence": _confidence(evidence),
            "severity": max((_severity(title) for title in titles), key=("info", "low", "medium", "high", "critical").index),
            "countries": countries,
            "sectors": sectors,
            "topics": topics,
            "evidence": evidence,
            "contradictions": contradictions,
        }
        events.append(_carry_times(event, previous_by_id.get(event_id), now_iso))
    events.sort(key=lambda row: row["id"])
    return {
        "schema_version": SCHEMA_VERSION,
        "updated": now_iso,
        "policy": "observed facts and conservative deterministic clustering; no paid model calls",
        "events": events,
    }


def _signal(
    signal_type: str,
    subject: str,
    *,
    title: str,
    title_en: str,
    facts: list[str],
    assessment: str,
    summary: str | None = None,
    observed_at: str | None = None,
    valid_until: str | None = None,
    inference: str = "",
    uncertainty: str,
    confidence: float,
    severity: str = "info",
    countries: list[str] | None = None,
    sectors: list[str] | None = None,
    topics: list[str] | None = None,
    evidence: list[dict[str, Any]] | None = None,
    contradictions: list[dict[str, Any]] | None = None,
    event_ids: list[str] | None = None,
) -> dict[str, Any]:
    evidence = sorted(evidence or [], key=lambda row: row["id"])
    if observed_at is None:
        dated = [
            (parsed, str(row.get("observed_at") or ""))
            for row in evidence
            if (parsed := _parse_ts(row.get("observed_at"))) is not None
        ]
        observed_at = max(dated, default=(None, ""))[1]
    result = {
        "id": _hash("sig_", signal_type + "|" + _normalize_text(subject)),
        "type": signal_type,
        "title": title,
        "title_en": title_en,
        "summary": summary or assessment,
        "observed_at": observed_at or "",
        "observed_facts": facts,
        "assessment": assessment,
        "inference": inference,
        "uncertainty": uncertainty,
        "confidence": round(max(0.0, min(1.0, confidence)), 2),
        "severity": severity,
        "countries": sorted(set(countries or [])),
        "sectors": sorted(set(sectors or [])),
        "topics": sorted(set(topics or [])),
        "evidence": evidence,
        "contradictions": sorted(contradictions or [], key=lambda row: row["id"]),
        "event_ids": sorted(set(event_ids or [])),
    }
    if valid_until:
        result["valid_until"] = valid_until
    return result


def _tension_signals(inputs: dict[str, dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    doc = inputs.get("tension") or {}
    if not _fresh(doc.get("updated"), now, TENSION_MAX_HOURS):
        return []
    out = []
    for country in doc.get("countries") or []:
        score = country.get("score")
        if not isinstance(score, (int, float)) or score < RISK_THRESHOLD:
            continue
        code = str(country.get("id") or "")
        evidence = []
        for item in (country.get("events") or []) + (country.get("signals") or []):
            title = item.get("h") or item.get("detail")
            at = item.get("at") or doc.get("updated")
            if title and _fresh(at, now, EVENT_MAX_HOURS):
                evidence.append(_evidence(
                    title, "", item.get("src"), item.get("g"), item.get("u") or item.get("url"),
                    at, "tension",
                ))
        name = country.get("name") or code
        out.append(_signal(
            "country-risk-threshold", code,
            title=f"{name}: SANAD tension score crossed {RISK_THRESHOLD}",
            title_en=f"{country.get('en') or code}: SANAD tension score crossed {RISK_THRESHOLD}",
            observed_at=str(doc.get("updated") or ""),
            facts=[f"Published tension score: {score}; published level: {country.get('level') or ''}."],
            assessment="The deterministic SANAD tension output crossed its documented export threshold.",
            inference="This is a threshold notification, not a prediction of violence or a government warning.",
            uncertainty="The score reflects the inputs and weights published by SANAD and can change as source coverage changes.",
            confidence=0.75 if evidence else 0.6,
            severity="high" if score >= 80 else "medium",
            countries=[code] if code else [],
            sectors=["government"],
            topics=["risk-threshold"],
            evidence=evidence,
        ))
    return out


def _watchlist_signals(inputs: dict[str, dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    doc = inputs.get("osint") or {}
    if not _fresh(doc.get("updated"), now, WATCH_MAX_HOURS):
        return []
    out = []
    for watch in doc.get("watches") or []:
        hits = []
        for item in watch.get("hits") or []:
            at = item.get("at") or doc.get("updated")
            if not _fresh(at, now, WATCH_MAX_HOURS):
                continue
            hits.append(_evidence(
                item.get("head"), item.get("he"), item.get("src"), item.get("grade"),
                item.get("link"), at, "osint",
            ))
        if not hits or int(watch.get("n_sanad") or 0) < 1 or int(watch.get("heat") or 0) < 50:
            continue
        term = str(watch.get("term") or "")
        out.append(_signal(
            "watchlist-match", term,
            title=f"Watch term active: {term}",
            title_en=f"Watch term active: {watch.get('en') or term}",
            observed_at=str(doc.get("updated") or ""),
            facts=[
                f"{watch.get('n_sanad') or 0} graded SANAD hit(s) and "
                f"{watch.get('n_open') or 0} attributable open-news hit(s); heat {watch.get('heat') or 0}."
            ],
            assessment="The configured public watch term met the minimum graded-hit and heat thresholds.",
            inference="Term matching indicates attention, not intent, coordination, or threat.",
            uncertainty="Keyword matching can include unrelated uses of the same term.",
            confidence=0.7,
            topics=[str(watch.get("topic") or term)],
            evidence=hits,
        ))
    return out


def _paper_signals(inputs: dict[str, dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    doc = inputs.get("papers") or {}
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in doc.get("items") or []:
        at = item.get("published") or doc.get("updated")
        if not _fresh(at, now, PAPER_MAX_HOURS):
            continue
        blob = " ".join(str(item.get(key) or "") for key in ("title", "abstract", "title_ar", "summary_ar"))
        for topic in _classify(blob, _AI_PAPER_TOPICS):
            groups.setdefault(topic, []).append(item)
    out = []
    for topic, items in groups.items():
        unique = {str(item.get("link") or item.get("id") or ""): item for item in items}
        if len(unique) < 2:
            continue
        evidence = [
            _evidence(
                item.get("title_ar") or item.get("title"), item.get("title"),
                item.get("src") or item.get("via") or "arXiv / Hugging Face", "",
                item.get("link"), item.get("published") or doc.get("updated"), "papers",
            )
            for item in unique.values()
        ]
        out.append(_signal(
            "ai-research-trend", topic,
            title=f"AI research concentration: {topic}",
            title_en=f"AI research concentration: {topic}",
            facts=[f"{len(evidence)} recent papers in the SANAD paper feed match the deterministic topic vocabulary."],
            assessment="A repeated research topic is present in recent attributed paper records.",
            inference="This is a publication-feed concentration, not a claim of field-wide consensus or impact.",
            uncertainty="Topic assignment is keyword-based and the feed is not an exhaustive literature review.",
            confidence=0.65,
            sectors=["technology"],
            topics=["artificial-intelligence", topic],
            evidence=evidence,
        ))
    return out


def _repo_signals(inputs: dict[str, dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    doc = inputs.get("repos") or {}
    if doc.get("status") != "live":
        return []
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in doc.get("items") or []:
        if not _fresh(item.get("pushed_at"), now, REPO_MAX_HOURS):
            continue
        fit = str(item.get("fit_en") or "AI repository")
        groups.setdefault(fit, []).append(item)
    out = []
    for fit, items in groups.items():
        unique = {str(item.get("full_name") or ""): item for item in items if item.get("full_name")}
        if len(unique) < 2:
            continue
        top = sorted(unique.values(), key=lambda item: (-float(item.get("score") or 0), item["full_name"]))[:8]
        evidence = [
            _evidence(
                item.get("full_name"), item.get("description"), "GitHub Search API", "",
                item.get("url"), item.get("pushed_at"), "repos",
            )
            for item in top
        ]
        out.append(_signal(
            "ai-repository-trend", fit,
            title=f"AI repository activity: {fit}",
            title_en=f"AI repository activity: {fit}",
            facts=[f"{len(evidence)} recently pushed, non-fork repositories share this SANAD radar classification."],
            assessment="The live GitHub radar contains a repeated repository class after deterministic ranking and deduplication.",
            inference="Repository activity and stars indicate attention, not code quality, safety, or suitability.",
            uncertainty="GitHub search coverage and popularity metrics are incomplete and can be gamed.",
            confidence=0.62,
            sectors=["technology"],
            topics=["artificial-intelligence", "open-source", _normalize_text(fit).replace(" ", "-")],
            evidence=evidence,
        ))
    return out


def build_signals(
    inputs: dict[str, dict[str, Any]],
    events_doc: dict[str, Any],
    *,
    now: datetime | None = None,
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now_dt = now or _now()
    now_iso = _iso(now_dt)
    previous_by_id = {row["id"]: row for row in (previous or {}).get("signals", []) if row.get("id")}
    signals = []
    for event in events_doc.get("events") or []:
        sources = {row.get("source_name") for row in event["evidence"] if row.get("source_name")}
        urls = {_canonical_url(row.get("url")) for row in event["evidence"] if _canonical_url(row.get("url"))}
        if event["contradictions"]:
            signals.append(_signal(
                "contradiction", event["id"],
                title="Contradictory attributable claims require review",
                title_en="Contradictory attributable claims require review",
                facts=event["observed_facts"],
                assessment="SANAD found an explicit denial paired with a substantially overlapping attributable headline.",
                inference="No resolution is inferred.",
                uncertainty="The contradiction is headline-level; consult every evidence link before deciding which claim is accurate.",
                confidence=event["confidence"],
                severity="medium",
                countries=event["countries"],
                sectors=event["sectors"],
                topics=event["topics"],
                evidence=event["evidence"],
                contradictions=event["contradictions"],
                event_ids=[event["id"]],
            ))
        if len(sources) >= 2 and len(urls) >= 2:
            signals.append(_signal(
                "multi-source-event", event["id"],
                title=event["title"],
                title_en=event["title_en"],
                facts=event["observed_facts"],
                assessment=f"{len(sources)} named sources and {len(urls)} distinct evidence URLs cluster conservatively.",
                inference="The sources may be reporting the same underlying event.",
                uncertainty=event["uncertainty"],
                confidence=event["confidence"],
                severity=event["severity"],
                countries=event["countries"],
                sectors=event["sectors"],
                topics=event["topics"],
                evidence=event["evidence"],
                contradictions=event["contradictions"],
                event_ids=[event["id"]],
            ))
    signals.extend(_tension_signals(inputs, now_dt))
    signals.extend(_watchlist_signals(inputs, now_dt))
    signals.extend(_paper_signals(inputs, now_dt))
    signals.extend(_repo_signals(inputs, now_dt))

    unique = {row["id"]: row for row in signals}
    final = []
    for signal_id in sorted(unique):
        final.append(_carry_times(unique[signal_id], previous_by_id.get(signal_id), now_iso))
    return {
        "schema_version": SCHEMA_VERSION,
        "updated": now_iso,
        "thresholds": {
            "country_risk_score": RISK_THRESHOLD,
            "watch_heat": 50,
            "multi_source_named_sources": 2,
        },
        "signals": final,
    }


def build_ontime_export(signals_doc: dict[str, Any]) -> dict[str, Any]:
    """Return the allowlisted, read-only downstream contract."""
    exported = []
    for signal in signals_doc.get("signals") or []:
        row = {key: signal.get(key) for key in _SIGNAL_FIELDS if key in signal}
        row["evidence"] = [
            {
                "source_ref": evidence.get("id"),
                "url": evidence.get("url"),
                "publisher": evidence.get("source_name"),
                "grade": evidence.get("source_grade"),
                "published_at": evidence.get("observed_at"),
                "title": evidence.get("title"),
                "title_en": evidence.get("title_en"),
                "dataset": evidence.get("dataset"),
            }
            for evidence in signal.get("evidence") or []
        ]
        row["contradictions"] = [
            {
                "id": item.get("id"),
                "type": item.get("type"),
                "summary": item.get("summary"),
                "evidence_ids": item.get("evidence_ids") or [],
            }
            for item in signal.get("contradictions") or []
        ]
        exported.append(row)
    cursor_records = []
    for signal in exported:
        cursor_records.append({
            key: value for key, value in signal.items()
            if key not in ("created_at", "updated_at")
        })
    cursor_payload = json.dumps(cursor_records, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    generated_at = signals_doc.get("updated") or ""
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "updated_at": generated_at,
        "cursor": "sha256:" + hashlib.sha256(cursor_payload.encode("utf-8")).hexdigest(),
        "producer": "SANAD",
        "authority": "SANAD",
        "read_only": True,
        "signals": exported,
    }


def _read_json(path: Path, *, required: bool = False) -> dict[str, Any]:
    if not path.exists():
        if required:
            raise FileNotFoundError(path)
        return {}
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=1), encoding="utf-8")
    temp.replace(path)


def generate_intelligence(out_dir: str | os.PathLike[str] | None = None, now: datetime | None = None) -> dict[str, Any]:
    target = Path(out_dir) if out_dir is not None else OUT
    target.mkdir(parents=True, exist_ok=True)
    names = ("news", "official", "osint", "map", "tension", "papers", "repos")
    inputs = {name: _read_json(target / f"{name}.json", required=name == "news") for name in names}
    previous_events = _read_json(target / "events.json")
    previous_signals = _read_json(target / "signals.json")
    events_doc = build_events(inputs, now=now, previous=previous_events)
    signals_doc = build_signals(inputs, events_doc, now=now, previous=previous_signals)
    export_doc = build_ontime_export(signals_doc)
    _write_json(target / "events.json", events_doc)
    _write_json(target / "signals.json", signals_doc)
    _write_json(target / "ontime-signals.json", export_doc)
    print(
        f"Intelligence signals: {len(events_doc['events'])} events, "
        f"{len(signals_doc['signals'])} approved signals"
    )
    return {
        "why": f"{len(events_doc['events'])} events / {len(signals_doc['signals'])} signals",
        "events": len(events_doc["events"]),
        "signals": len(signals_doc["signals"]),
    }


def intelligence_signals() -> dict[str, Any]:
    return generate_intelligence()


if __name__ == "__main__":
    print(json.dumps(intelligence_signals(), ensure_ascii=False))
