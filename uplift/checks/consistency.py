#!/usr/bin/env python3
"""Package consistency gate. Every metric owned, every task listed, every
task measurable. Runs from anywhere — paths resolve against this file."""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

fail = []
prompts = sorted(f for f in os.listdir('prompts') if f.endswith('.md'))
tasks   = [f for f in prompts if f != '00-context.md']
base    = json.load(open('baseline.json'))
readme  = open('README.md').read()

# 1 — every owner in baseline maps to a real task file
owners = {m['owner'] for m in base['metrics'].values()}
for o in sorted(owners):
    if o == 'all':
        continue
    if not any(t.startswith(o.split('-')[0]) for t in tasks):
        fail.append(f"baseline owner «{o}» has no task file")

# 2 — every task owns at least one metric
for t in tasks:
    stem = t[:-3]
    if not any(m['owner'] in (stem, stem.split('-')[0]) or stem.startswith(m['owner'].split('-')[0])
               for m in base['metrics'].values()):
        fail.append(f"task {t} owns no metric — it cannot be measured")

# 3 — every task is listed in the README
for t in tasks:
    if t not in readme:
        fail.append(f"task {t} missing from README")

# 4 — every task ends with a Definition of done
for t in tasks:
    if 'Definition of done' not in open(f'prompts/{t}').read():
        fail.append(f"task {t} has no Definition of done")

# 5 — every task carries a measured number, not just prose
for t in tasks:
    body = open(f'prompts/{t}').read()
    if not re.search(r'\d{2,}', body):
        fail.append(f"task {t} cites no measured figure")

print(f"  tasks: {len(tasks)}   metrics: {len(base['metrics'])}   owners: {len(owners)}")
if fail:
    print("\n⛔ inconsistent:")
    for f in fail: print("   -", f)
    sys.exit(1)
print("\n✅ package consistent")
