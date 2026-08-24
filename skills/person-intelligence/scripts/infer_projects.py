#!/usr/bin/env python3
"""Infer project associations from goals, actions, and topics.

Reads JSON from stdin with keys: goals, actions, topics, person_name.
Outputs JSON to stdout with confirmed (3+ matches) and suggested (1-2 matches) projects.
"""

import json
import os
import re
import sys


def load_keyword_map():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    map_path = os.path.join(script_dir, "..", "references", "project-keyword-map.json")
    with open(map_path, "r") as f:
        data = json.load(f)
    # Remove _meta key
    data.pop("_meta", None)
    return data


def _matcher(keyword):
    """Compile a keyword into a WORD-BOUNDARY matcher.

    Plain substring matching silently mis-attributed projects. Two real cases from the
    2026-08-23 sweep: the keyword `HR` matched "Ant**hr**opic billing review" and tagged it
    `people-ops`; `board` matched "dash**board** redesign" and tagged it
    `board-intelligence`. Nothing errored — the wrong project just appeared in a person's
    profile with the sentence as its evidence, which reads as a finding.

    Acronyms are additionally matched CASE-SENSITIVELY. An all-caps keyword of five
    characters or fewer is an initialism (HR, CAC, LTV, ARPM, MVP, JIRA, CPO, COO, TAM, CPM,
    NCO); lowercasing those makes them collide with ordinary words far more often than it
    catches a real mention.
    """
    flags = 0 if (keyword.isupper() and len(keyword) <= 5) else re.IGNORECASE
    return re.compile(r"\b" + re.escape(keyword) + r"\b", flags)


def truncate(text, length=80):
    if len(text) <= length:
        return text
    return text[:length - 3] + "..."


def infer_projects(input_data):
    keyword_map = load_keyword_map()
    compiled = {p: [_matcher(k) for k in kws] for p, kws in keyword_map.items()}

    # Collect all input items
    all_items = []
    for key in ("goals", "actions", "topics"):
        for item in input_data.get(key, []):
            all_items.append(item)

    results = {}

    for project, matchers in compiled.items():
        matches = 0
        evidence = []

        for item in all_items:
            if any(m.search(item) for m in matchers):
                matches += 1
                evidence.append(truncate(item))

        if matches > 0:
            results[project] = {"project": project, "matches": matches, "evidence": evidence}

    confirmed = sorted(
        [r for r in results.values() if r["matches"] >= 3],
        key=lambda x: x["matches"],
        reverse=True,
    )
    suggested = sorted(
        [r for r in results.values() if 1 <= r["matches"] <= 2],
        key=lambda x: x["matches"],
        reverse=True,
    )

    return {"confirmed": confirmed, "suggested": suggested}


if __name__ == "__main__":
    input_data = json.load(sys.stdin)
    output = infer_projects(input_data)
    print(json.dumps(output, indent=2))
