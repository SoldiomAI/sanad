#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI repo radar for SANAD.

Produces ``daily/repos.json`` from public GitHub Search results. The ranking is
not a black-box "GitHub Trending" scrape: it is an auditable daily scan of AI,
LLM, RAG, and agent repositories that were created recently or pushed recently.
Each entry carries a plain-language explanation and a concrete work-case use.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path


OUT = Path(os.environ.get("SANAD_DAILY", "daily"))
REPOS_F = OUT / "repos.json"
MAX_REPOS = int(os.environ.get("SANAD_REPOS_MAX", "10"))
UA = "SANAD-AI-Repo-Radar/1.0 (+https://isnad.news)"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="minutes")


def _cut(s: object, n: int) -> str:
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s[: n - 1] + "…" if len(s) > n else s


def _request_json(url: str, timeout: int = 20) -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": UA,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _search_repos(query: str, per_page: int = 12) -> list[dict]:
    qs = urllib.parse.urlencode(
        {"q": query, "sort": "stars", "order": "desc", "per_page": str(per_page)}
    )
    data = _request_json("https://api.github.com/search/repositories?" + qs)
    return [x for x in data.get("items", []) if isinstance(x, dict)]


def _days_since(iso: str) -> float:
    try:
        return max(0.0, (_now() - datetime.fromisoformat(iso.replace("Z", "+00:00"))).total_seconds() / 86400)
    except Exception:
        return 999.0


def _repo_score(repo: dict) -> float:
    stars = int(repo.get("stargazers_count") or 0)
    forks = int(repo.get("forks_count") or 0)
    pushed_days = _days_since(str(repo.get("pushed_at") or ""))
    created_days = _days_since(str(repo.get("created_at") or ""))
    fresh_bonus = max(0, 30 - min(pushed_days, 30)) * 35
    new_bonus = max(0, 120 - min(created_days, 120)) * 6
    return stars + forks * 2 + fresh_bonus + new_bonus


def _classify_repo(repo: dict) -> dict:
    topics = " ".join(repo.get("topics") or [])
    blob = f"{repo.get('name','')} {repo.get('description','')} {topics}".lower()
    if any(k in blob for k in ("rag", "retrieval", "vector", "embedding", "knowledge")):
        return {
            "fit_ar": "استرجاع ومعرفة",
            "fit_en": "RAG / knowledge",
            "why_ar": "يربط النموذج بمصادر معرفة قابلة للتتبع بدل الإجابة من الذاكرة وحدها.",
            "why_en": "Connects a model to traceable knowledge instead of relying on memory alone.",
            "use_case_ar": "استخدمه لبناء باحث داخلي يقرأ أرشيف سَنَد أو وثائق المؤسسة ثم يجيب مع روابط المصادر.",
            "use_case_en": "Use it to build an internal researcher over SANAD archives or company docs with source links.",
        }
    if any(k in blob for k in ("agent", "agents", "workflow", "orchestration", "tool-use", "multi-agent")):
        return {
            "fit_ar": "وكلاء وسير عمل",
            "fit_en": "Agents / workflows",
            "why_ar": "يحوّل النموذج من محادثة واحدة إلى عامل ينفّذ خطوات وأدوات ويتابع الحالة.",
            "why_en": "Turns a model from a single chat into a worker that runs steps, tools, and state.",
            "use_case_ar": "جرّبه كقالب لوكيل يرصد خبرًا، يتحقق من الرابط، يكتب ملخصًا، ثم يرسل تنبيهًا قابلًا للمراجعة.",
            "use_case_en": "Use it as a template for an agent that watches a story, verifies the URL, summarizes it, then queues an alert.",
        }
    if any(k in blob for k in ("inference", "serving", "llm", "model", "transformer", "fine-tun")):
        return {
            "fit_ar": "نماذج وتشغيل",
            "fit_en": "Models / inference",
            "why_ar": "يعالج طبقة تشغيل النماذج: الاستدعاء، الأداء، أو الضبط، وهي أساس أي منتج ذكاء حي.",
            "why_en": "Covers model runtime, performance, or tuning—the base layer for a live AI product.",
            "use_case_ar": "استخدمه لاختبار نموذج محلي أو خدمة استدلال قبل ربطها بوكيل التحرير أو الفاحص.",
            "use_case_en": "Use it to test a local model or inference service before connecting it to an editor or verifier agent.",
        }
    if any(k in blob for k in ("image", "video", "audio", "vision", "diffusion", "multimodal")):
        return {
            "fit_ar": "وسائط متعددة",
            "fit_en": "Multimodal",
            "why_ar": "يفتح باب فحص الصور والفيديو والصوت أو إنتاج وسائط مرافقة بمصدر واضح.",
            "why_en": "Supports image, video, or audio inspection/generation with explicit provenance.",
            "use_case_ar": "جرّبه لتحليل صورة خبرية أو إنتاج بطاقة توضيحية مع بقاء الرابط الأصلي ظاهرًا.",
            "use_case_en": "Use it to inspect a news image or generate an explainer card while keeping the original source visible.",
        }
    if any(k in blob for k in ("eval", "benchmark", "test", "guardrail", "safety")):
        return {
            "fit_ar": "اختبار وحوكمة",
            "fit_en": "Evaluation / safety",
            "why_ar": "يساعد على قياس جودة مخرجات الذكاء بدل الاكتفاء بانطباع عام.",
            "why_en": "Measures AI output quality instead of relying on impressions.",
            "use_case_ar": "استخدمه كحارس يقيس هل ملخصات الأخبار تلتزم بالمصدر ولا تضيف ادعاءات جديدة.",
            "use_case_en": "Use it as a guard that checks whether news summaries stay grounded and add no new claims.",
        }
    return {
        "fit_ar": "تطبيق ذكاء اصطناعي",
        "fit_en": "AI application",
        "why_ar": "مشروع نشط يمكن تحويله إلى تجربة عملية أو درس هندسي قابل للتشغيل.",
        "why_en": "An active project that can become a runnable prototype or engineering case study.",
        "use_case_ar": "ابدأ بقراءة الترخيص وملف README، شغّل المثال الرسمي، ثم طبّقه على ملف بيانات صغير من عملك.",
        "use_case_en": "Start with the license and README, run the official quickstart, then apply it to a small dataset from your work.",
    }


def _normalize_repo(repo: dict, query: str) -> dict:
    cls = _classify_repo(repo)
    topics = [str(t) for t in repo.get("topics") or []][:8]
    return {
        "name": repo.get("name") or "",
        "full_name": repo.get("full_name") or "",
        "url": repo.get("html_url") or "",
        "description": _cut(repo.get("description") or "", 220),
        "language": repo.get("language") or "",
        "stars": int(repo.get("stargazers_count") or 0),
        "forks": int(repo.get("forks_count") or 0),
        "open_issues": int(repo.get("open_issues_count") or 0),
        "created_at": repo.get("created_at") or "",
        "pushed_at": repo.get("pushed_at") or "",
        "topics": topics,
        "license": ((repo.get("license") or {}).get("spdx_id") or "").replace("NOASSERTION", ""),
        "score": round(_repo_score(repo), 2),
        "basis": query,
        **cls,
        "steps_ar": [
            "افحص الترخيص وملف README قبل إدخاله في عملك.",
            "شغّل مثالًا صغيرًا في فرع تجريبي أو حاوية منفصلة.",
            "حوّله إلى حالة عمل: مدخلاتك، مخرجات قابلة للقياس، ومراجع واضحة.",
        ],
        "steps_en": [
            "Check the license and README before using it at work.",
            "Run a tiny quickstart in a sandbox branch or container.",
            "Turn it into a work case: your inputs, measurable outputs, and clear references.",
        ],
    }


def build_repo_list(raw: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for repo in sorted(raw, key=_repo_score, reverse=True):
        if repo.get("fork") or repo.get("archived"):
            continue
        key = (repo.get("full_name") or "").lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(_normalize_repo(repo, str(repo.get("_query") or "")))
        if len(out) >= MAX_REPOS:
            break
    return out


def _fallback_repos() -> list[dict]:
    rows = [
        ("langchain-ai/langchain", "Build context-aware reasoning and tool workflows.", "Python", 116000, "Agents / workflows"),
        ("ollama/ollama", "Run open models locally for private prototyping.", "Go", 155000, "Models / inference"),
        ("microsoft/autogen", "Create multi-agent conversations and task workflows.", "Python", 49000, "Agents / workflows"),
        ("open-webui/open-webui", "Ship a local AI chat workspace for teams.", "Python", 111000, "AI application"),
    ]
    now = _iso(_now())
    out = []
    for full, desc, lang, stars, fit in rows:
        name = full.split("/", 1)[1]
        repo = {
            "name": name,
            "full_name": full,
            "html_url": "https://github.com/" + full,
            "description": desc,
            "language": lang,
            "stargazers_count": stars,
            "forks_count": 0,
            "open_issues_count": 0,
            "created_at": now,
            "pushed_at": now,
            "topics": [fit.lower().replace(" / ", "-").replace(" ", "-")],
            "_query": "curated fallback",
        }
        out.append(_normalize_repo(repo, "curated fallback"))
    return out[:MAX_REPOS]


def ai_repos() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    pushed = (_now() - timedelta(days=30)).date().isoformat()
    created = (_now() - timedelta(days=120)).date().isoformat()
    queries = [
        f"topic:artificial-intelligence pushed:>={pushed} stars:>500 archived:false fork:false",
        f"topic:llm pushed:>={pushed} stars:>500 archived:false fork:false",
        f"topic:ai-agents pushed:>={pushed} stars:>100 archived:false fork:false",
        f"topic:rag pushed:>={pushed} stars:>100 archived:false fork:false",
        f"topic:ai created:>={created} stars:>25 archived:false fork:false",
    ]
    raw: list[dict] = []
    errors = []
    for q in queries:
        try:
            for repo in _search_repos(q):
                repo["_query"] = q
                raw.append(repo)
            time.sleep(0.25)
        except Exception as e:
            errors.append(str(e)[:90])
    items = build_repo_list(raw)
    status = "live" if items else "fallback"
    if not items:
        items = _fallback_repos()
    out = {
        "updated": _iso(_now()),
        "source": "GitHub Search API" if status == "live" else "curated fallback",
        "basis_ar": "مستودعات ذكاء اصطناعي وLLM وRAG ووكلاء، دُفعت حديثًا أو أُنشئت حديثًا، مرتبة بالنجوم والنشاط.",
        "basis_en": "AI, LLM, RAG, and agent repositories recently pushed or newly created, ranked by stars and freshness.",
        "status": status,
        "errors": errors[:3],
        "items": items,
        "n": len(items),
    }
    REPOS_F.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"AI repo radar: {len(items)} repos - {status}")
    return {"why": f"{len(items)} repos · {status}", "items": len(items)}


if __name__ == "__main__":
    print(json.dumps(ai_repos(), ensure_ascii=True))
