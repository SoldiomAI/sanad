#!/usr/bin/env python3
"""Refuse publishing hollow or identical-collector social dumps to sanad-data."""
import json
import sys
from pathlib import Path

ROOT = Path("daily")


def load(name):
    p = ROOT / name
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"❌ {p}: {e}")
        sys.exit(1)


def main():
    soft = "--soft" in sys.argv
    for need in ("posts.json", "comments.json", "bundle.json"):
        load(need)
    b = load("bundle.json")
    if "posts" not in b or "comments" not in b:
        print("❌ bundle.json missing posts/comments")
        if soft:
            print("⚠️ soft: will keep remote social files")
            sys.exit(2)
        sys.exit(1)
    ag = (b.get("posts") or {}).get("agents") or {}

    def links(aid):
        return [
            (p.get("link") or p.get("title"))
            for p in (ag.get(aid) or {}).get("posts") or []
            if (p.get("kind") or "news") == "news"
        ]

    h, r = links("hurr"), links("rasid")
    if len(h) >= 10 and h == r:
        print("❌ identical collector dumps (hurr==rasid)")
        if soft:
            print("⚠️ soft: will keep remote social files")
            sys.exit(2)
        sys.exit(1)
    print(
        f"✅ social ok · posts n={(b.get('posts') or {}).get('n')} · "
        f"comments n={(b.get('comments') or {}).get('n')}"
    )


if __name__ == "__main__":
    main()
