# -*- coding: utf-8 -*-
import unittest

from pipeline.ai_repos import _classify_repo, build_repo_list


class TestAiRepoRadar(unittest.TestCase):
    def test_rag_repo_gets_work_case(self):
        repo = {
            "name": "news-rag",
            "description": "RAG over documents with vector retrieval",
            "topics": ["rag", "vector-search"],
        }
        c = _classify_repo(repo)
        self.assertEqual(c["fit_en"], "RAG / knowledge")
        self.assertIn("أرشيف", c["use_case_ar"])

    def test_agents_repo_gets_agent_workflow_case(self):
        repo = {
            "name": "agent-runner",
            "description": "Multi-agent workflow orchestration with tool-use",
            "topics": ["agents"],
        }
        c = _classify_repo(repo)
        self.assertEqual(c["fit_en"], "Agents / workflows")
        self.assertIn("يتحقق", c["use_case_ar"])

    def test_build_repo_list_dedupes_and_skips_forks(self):
        raw = [
            {
                "name": "a",
                "full_name": "org/a",
                "html_url": "https://github.com/org/a",
                "description": "LLM inference",
                "stargazers_count": 100,
                "forks_count": 2,
                "open_issues_count": 0,
                "created_at": "2026-08-01T00:00:00Z",
                "pushed_at": "2026-08-29T00:00:00Z",
                "topics": ["llm"],
                "fork": False,
                "archived": False,
            },
            {
                "name": "a",
                "full_name": "org/a",
                "html_url": "https://github.com/org/a",
                "description": "duplicate",
                "stargazers_count": 10,
                "forks_count": 0,
                "created_at": "2026-08-01T00:00:00Z",
                "pushed_at": "2026-08-29T00:00:00Z",
                "topics": [],
            },
            {
                "name": "forked",
                "full_name": "org/forked",
                "fork": True,
                "archived": False,
                "stargazers_count": 999,
                "created_at": "2026-08-01T00:00:00Z",
                "pushed_at": "2026-08-29T00:00:00Z",
            },
        ]
        items = build_repo_list(raw)
        self.assertEqual([x["full_name"] for x in items], ["org/a"])
        self.assertEqual(items[0]["fit_en"], "Models / inference")


if __name__ == "__main__":
    unittest.main()
