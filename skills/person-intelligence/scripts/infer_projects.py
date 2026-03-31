#!/usr/bin/env python3
"""Infer project associations from goals, actions, and topics.

Reads JSON from stdin with keys: goals, actions, topics, person_name.
Outputs JSON to stdout with confirmed (3+ matches) and suggested (1-2 matches) projects.
"""

import json
import os
import sys


def load_keyword_map():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    map_path = os.path.join(script_dir, "..", "references", "project-keyword-map.json")
    with open(map_path, "r") as f:
        data = json.load(f)
    # Remove _meta key
    data.pop("_meta", None)
    return data


def truncate(text, length=80):
    if len(text) <= length:
        return text
    return text[:length - 3] + "..."


def infer_projects(input_data):
    keyword_map = load_keyword_map()

    # Collect all input items
    all_items = []
    for key in ("goals", "actions", "topics"):
        for item in input_data.get(key, []):
            all_items.append(item)

    results = {}

    for project, keywords in keyword_map.items():
        matches = 0
        evidence = []

        for item in all_items:
            item_lower = item.lower()
            matched = False
            for kw in keywords:
                if kw.lower() in item_lower:
                    matched = True
                    break
            if matched:
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
