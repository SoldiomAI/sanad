# -*- coding: utf-8 -*-
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pipeline.intelligence_signals import (
    build_events,
    build_ontime_export,
    build_signals,
    generate_intelligence,
)


NOW = datetime(2026, 8, 30, 0, 0, tzinfo=timezone.utc)
RECENT = (NOW - timedelta(hours=2)).isoformat()
STALE = (NOW - timedelta(days=10)).isoformat()


def story(head, source, url, grade="حسن", at=RECENT):
    return {
        "head": head,
        "he": "",
        "src": source,
        "grade": grade,
        "link": url,
        "at": at,
    }


def base_inputs():
    return {
        "news": {
            "updated": RECENT,
            "cats": {
                "صحة": [
                    story(
                        "وزارة الصحة تعلن إغلاق مستشفى النور",
                        "وكالة ألف",
                        "https://example.com/assertion",
                    ),
                    story(
                        "وزارة الصحة تنفي إغلاق مستشفى النور",
                        "وكالة باء",
                        "https://example.net/denial",
                        grade="صحيح",
                    ),
                ]
            },
        },
        "official": {"updated": RECENT, "src": []},
        "osint": {"updated": RECENT, "watches": []},
        "map": {"updated": RECENT, "countries": []},
        "tension": {"updated": RECENT, "countries": []},
        "papers": {"updated": RECENT, "items": []},
        "repos": {"updated": RECENT, "status": "live", "items": []},
    }


class TestEventClustering(unittest.TestCase):
    def test_clusters_related_claims_and_marks_contradiction(self):
        events = build_events(base_inputs(), now=NOW)["events"]
        self.assertEqual(len(events), 1)
        self.assertEqual(len(events[0]["evidence"]), 2)
        self.assertEqual(events[0]["contradictions"][0]["type"], "explicit-denial")

    def test_duplicate_evidence_is_deduped_without_losing_provenance(self):
        inputs = base_inputs()
        duplicate = dict(inputs["news"]["cats"]["صحة"][0])
        inputs["osint"]["watches"] = [{
            "term": "الصحة",
            "topic": "صحة",
            "hits": [{**duplicate, "channel": "sanad"}],
        }]
        event = build_events(inputs, now=NOW)["events"][0]
        evidence = [row for row in event["evidence"] if row["url"].endswith("/assertion")]
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0]["source_name"], "وكالة ألف")
        self.assertEqual(evidence[0]["source_grade"], "حسن")
        self.assertEqual(evidence[0]["observed_at"], RECENT)

    def test_ids_are_stable_when_input_order_changes(self):
        inputs = base_inputs()
        first = build_events(inputs, now=NOW)
        inputs["news"]["cats"]["صحة"].reverse()
        second = build_events(inputs, now=NOW)
        self.assertEqual(
            [event["id"] for event in first["events"]],
            [event["id"] for event in second["events"]],
        )
        self.assertEqual(
            [row["id"] for row in first["events"][0]["evidence"]],
            [row["id"] for row in second["events"][0]["evidence"]],
        )

    def test_stale_observations_are_suppressed(self):
        inputs = base_inputs()
        inputs["news"]["cats"]["صحة"].append(
            story("خبر قديم يجب ألا يظهر", "مصدر قديم", "https://old.example/item", at=STALE)
        )
        events = build_events(inputs, now=NOW)["events"]
        self.assertFalse(any("قديم" in fact for event in events for fact in event["observed_facts"]))

    def test_created_and_updated_times_survive_unchanged_content(self):
        first = build_events(base_inputs(), now=NOW)
        later = build_events(base_inputs(), now=NOW + timedelta(minutes=30), previous=first)
        self.assertEqual(first["events"][0]["created_at"], later["events"][0]["created_at"])
        self.assertEqual(first["events"][0]["updated_at"], later["events"][0]["updated_at"])

    def test_existing_id_survives_new_cluster_evidence(self):
        inputs = base_inputs()
        first = build_events(inputs, now=NOW)
        inputs["news"]["cats"]["صحة"].append(
            story(
                "إغلاق مستشفى النور بحسب تقرير جديد لوزارة الصحة",
                "وكالة جيم",
                "https://example.org/follow-up",
            )
        )
        later = build_events(inputs, now=NOW + timedelta(minutes=30), previous=first)
        self.assertEqual(first["events"][0]["id"], later["events"][0]["id"])
        self.assertEqual(first["events"][0]["created_at"], later["events"][0]["created_at"])


class TestSignalGeneration(unittest.TestCase):
    def test_contradiction_and_multi_source_signals_are_emitted(self):
        inputs = base_inputs()
        events = build_events(inputs, now=NOW)
        types = {signal["type"] for signal in build_signals(inputs, events, now=NOW)["signals"]}
        self.assertIn("contradiction", types)
        self.assertIn("multi-source-event", types)

    def test_supported_threshold_and_ai_signals_are_emitted(self):
        inputs = base_inputs()
        inputs["tension"] = {
            "updated": RECENT,
            "countries": [{
                "id": "kw",
                "name": "الكويت",
                "en": "Kuwait",
                "score": 65,
                "level": "مرتفع",
                "events": [{
                    "h": "بيان رسمي عن حالة الطقس",
                    "src": "كونا",
                    "g": "صحيح",
                    "u": "https://kuna.example/weather",
                    "at": RECENT,
                }],
                "signals": [],
            }],
        }
        inputs["osint"] = {
            "updated": RECENT,
            "watches": [{
                "term": "#الكويت",
                "en": "#Kuwait",
                "topic": "الكويت",
                "heat": 80,
                "n_sanad": 1,
                "n_open": 0,
                "hits": [story("الكويت تعلن تحديثا", "كونا", "https://kuna.example/update", "صحيح")],
            }],
        }
        inputs["papers"] = {
            "updated": RECENT,
            "items": [
                {
                    "id": "1",
                    "title": "Tool Use for Language Model Agents",
                    "link": "https://arxiv.org/abs/1",
                    "published": RECENT,
                },
                {
                    "id": "2",
                    "title": "Reliable Multi-Agent Planning",
                    "link": "https://arxiv.org/abs/2",
                    "published": RECENT,
                },
            ],
        }
        inputs["repos"] = {
            "updated": RECENT,
            "status": "live",
            "items": [
                {
                    "full_name": "org/a",
                    "description": "Agent framework",
                    "url": "https://github.com/org/a",
                    "pushed_at": RECENT,
                    "fit_en": "Agents / workflows",
                    "score": 10,
                },
                {
                    "full_name": "org/b",
                    "description": "Agent runtime",
                    "url": "https://github.com/org/b",
                    "pushed_at": RECENT,
                    "fit_en": "Agents / workflows",
                    "score": 9,
                },
            ],
        }
        events = build_events(inputs, now=NOW)
        types = {signal["type"] for signal in build_signals(inputs, events, now=NOW)["signals"]}
        self.assertTrue({
            "country-risk-threshold",
            "watchlist-match",
            "ai-research-trend",
            "ai-repository-trend",
        }.issubset(types))

    def test_repo_fallback_does_not_become_a_trend(self):
        inputs = base_inputs()
        inputs["repos"] = {
            "updated": RECENT,
            "status": "fallback",
            "items": [
                {"full_name": "org/a", "fit_en": "Agents / workflows", "pushed_at": RECENT},
                {"full_name": "org/b", "fit_en": "Agents / workflows", "pushed_at": RECENT},
            ],
        }
        events = build_events(inputs, now=NOW)
        signals = build_signals(inputs, events, now=NOW)["signals"]
        self.assertNotIn("ai-repository-trend", {row["type"] for row in signals})

    def test_export_is_an_allowlist_and_preserves_evidence(self):
        inputs = base_inputs()
        events = build_events(inputs, now=NOW)
        signals = build_signals(inputs, events, now=NOW)
        signals["signals"][0]["internal_prompt"] = "do not export"
        signals["signals"][0]["credentials"] = "do not export"
        signals["signals"][0]["evidence"][0]["raw_control_state"] = {"secret": True}
        export = build_ontime_export(signals)
        encoded = json.dumps(export, ensure_ascii=False)
        self.assertNotIn("internal_prompt", encoded)
        self.assertNotIn("credentials", encoded)
        self.assertNotIn("raw_control_state", encoded)
        self.assertEqual(export["schema_version"], "1.0")
        self.assertTrue(export["read_only"])
        self.assertTrue(export["cursor"].startswith("sha256:"))
        self.assertEqual(export["updated_at"], export["generated_at"])
        self.assertIn("summary", export["signals"][0])
        self.assertIn("observed_at", export["signals"][0])
        self.assertIn("assessment", export["signals"][0])
        self.assertIn("source_ref", export["signals"][0]["evidence"][0])
        self.assertIn("publisher", export["signals"][0]["evidence"][0])
        self.assertIn("published_at", export["signals"][0]["evidence"][0])
        self.assertEqual(
            export["signals"][0]["evidence"][0]["url"],
            signals["signals"][0]["evidence"][0]["url"],
        )

    def test_cursor_ignores_generation_time(self):
        inputs = base_inputs()
        events = build_events(inputs, now=NOW)
        signals = build_signals(inputs, events, now=NOW)
        first = build_ontime_export(signals)
        signals["updated"] = (NOW + timedelta(hours=1)).isoformat()
        second = build_ontime_export(signals)
        self.assertEqual(first["cursor"], second["cursor"])


class TestPipelineIntegration(unittest.TestCase):
    def test_generator_writes_all_three_products(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, doc in base_inputs().items():
                (root / f"{name}.json").write_text(
                    json.dumps(doc, ensure_ascii=False), encoding="utf-8"
                )
            generate_intelligence(root, now=NOW)
            for name in ("events", "signals", "ontime-signals"):
                path = root / f"{name}.json"
                self.assertTrue(path.exists())
                self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["schema_version"], "1.0")

    def test_daily_runner_calls_generator_before_health_in_every_path(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "pipeline" / "daily_anchor.py").read_text(encoding="utf-8")
        generator = '_run_aux("intelligence_signals","intelligence_signals","intelligence_signals")'
        self.assertEqual(source.count(generator), 3)
        position = 0
        for _ in range(3):
            generated_at = source.index(generator, position)
            health_at = source.index("hirasa()", generated_at)
            self.assertLess(generated_at, health_at)
            position = generated_at + len(generator)
        for key in ('"events"', '"signals"', '"ontime-signals"'):
            self.assertIn(key, source)
        self.assertIn('"events":   (3,   0,  "events", "intelligence_signals")', source)
        self.assertIn('doc.get("updated") or doc.get("updated_at") or doc.get("generated_at")', source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
