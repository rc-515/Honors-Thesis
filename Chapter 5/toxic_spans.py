#!/usr/bin/env python3
"""
Top Toxic Spans Finder
========================
Finds the highest-toxicity 50-message windows in each streamer's chat.

Usage:
    python toxic_spans.py --input master_results/
"""

import csv
import json
import sys
import argparse
import statistics
from pathlib import Path
from datetime import datetime


def load_scored(path):
    with open(path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        try:
            r["_tox"] = float(r["TOXICITY"])
        except:
            r["_tox"] = 0.0
    rows.sort(key=lambda r: r.get("createdAt", ""))
    return rows


def dedup(rows, window=10):
    """Remove spam: same user repeating, or same text 3+ times in window."""
    deduped = []
    recent = []
    for i, row in enumerate(rows):
        text = row.get("clean_text", row.get("content", "")).strip().lower()
        uid = row.get("userId", "")
        is_spam = False
        if i > 0:
            prev = rows[i - 1]
            prev_text = prev.get("clean_text", prev.get("content", "")).strip().lower()
            if prev.get("userId") == uid and prev_text == text and text:
                is_spam = True
        if not is_spam and text and len(text) > 2:
            if sum(1 for t in recent[-window:] if t == text) >= 2:
                is_spam = True
        recent.append(text)
        if len(recent) > window:
            recent.pop(0)
        if not is_spam:
            deduped.append(row)
    return deduped


def find_spans(rows, window=50, top_n=5):
    if len(rows) < window:
        return []

    spans = []
    for i in range(0, len(rows) - window + 1, window // 4):  # 25% overlap
        chunk = rows[i:i + window]
        mean_tox = statistics.mean(r["_tox"] for r in chunk)
        spans.append((mean_tox, i, chunk))

    # Sort by toxicity, take top N, but skip overlapping windows
    spans.sort(key=lambda x: x[0], reverse=True)
    selected = []
    used_indices = set()

    for mean_tox, start_idx, chunk in spans:
        # Check overlap with already-selected spans
        span_range = set(range(start_idx, start_idx + window))
        if span_range & used_indices:
            continue

        used_indices.update(span_range)

        # Time range
        ts_start = chunk[0].get("createdAt", "")
        ts_end = chunk[-1].get("createdAt", "")

        # Duration
        try:
            dt_start = datetime.fromisoformat(ts_start.replace("Z", "+00:00"))
            dt_end = datetime.fromisoformat(ts_end.replace("Z", "+00:00"))
            dur_sec = (dt_end - dt_start).total_seconds()
        except:
            dur_sec = None

        # Unique users
        users = set(r.get("userId", r.get("username", "")) for r in chunk)

        # Top 5 most toxic messages in this span
        sorted_by_tox = sorted(chunk, key=lambda r: r["_tox"], reverse=True)
        top_msgs = []
        for r in sorted_by_tox[:5]:
            text = r.get("clean_text", r.get("content", r.get("message", "")))[:150]
            top_msgs.append({
                "text": text,
                "toxicity": round(r["_tox"], 4),
                "user": r.get("username", r.get("userId", "?")),
            })

        # Attribute breakdown
        attr_means = {}
        for attr in ["INSULT", "PROFANITY", "IDENTITY_ATTACK", "THREAT"]:
            vals = []
            for r in chunk:
                try:
                    vals.append(float(r[attr]))
                except:
                    pass
            if vals:
                attr_means[attr] = round(statistics.mean(vals), 4)

        # Dominant attribute
        dominant = max(attr_means, key=attr_means.get) if attr_means else "?"

        selected.append({
            "rank": len(selected) + 1,
            "mean_toxicity": round(mean_tox, 4),
            "start": ts_start,
            "end": ts_end,
            "duration_seconds": round(dur_sec, 1) if dur_sec else None,
            "n_unique_users": len(users),
            "dominant_attribute": dominant,
            "attribute_means": attr_means,
            "pct_above_05": round(sum(1 for r in chunk if r["_tox"] > 0.5) / window * 100, 1),
            "pct_above_07": round(sum(1 for r in chunk if r["_tox"] > 0.7) / window * 100, 1),
            "top_messages": top_msgs,
        })

        if len(selected) >= top_n:
            break

    return selected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", "-i", required=True, help="master_results/ directory")
    parser.add_argument("--window", "-w", type=int, default=50)
    parser.add_argument("--top", "-n", type=int, default=5)
    args = parser.parse_args()

    root = Path(args.input)

    print("=" * 70)
    print(f"  TOP {args.top} TOXIC {args.window}-MESSAGE SPANS PER STREAMER")
    print("=" * 70)

    all_results = {}

    for sdir in sorted(root.iterdir()):
        if not sdir.is_dir():
            continue
        csv_path = sdir / "scored_messages.csv"
        if not csv_path.exists():
            continue

        name = sdir.name
        rows = load_scored(csv_path)
        if not rows:
            continue

        n_orig = len(rows)
        rows = dedup(rows)
        n_spam = n_orig - len(rows)

        spans = find_spans(rows, window=args.window, top_n=args.top)
        all_results[name] = spans

        print(f"\n{'='*70}")
        print(f"  {name} ({n_orig:,} scored, {n_spam:,} spam removed, {len(rows):,} remaining)")
        print(f"{'='*70}")

        for s in spans:
            dur = f"{s['duration_seconds']:.0f}s" if s['duration_seconds'] else "?"
            print(f"\n  #{s['rank']}  Mean toxicity: {s['mean_toxicity']:.4f}  "
                  f"({dur}, {s['n_unique_users']} users, "
                  f"{s['pct_above_05']}% >0.5, {s['pct_above_07']}% >0.7)")
            print(f"       {s['start']} → {s['end']}")
            print(f"       Dominant: {s['dominant_attribute']}  "
                  f"(INS={s['attribute_means'].get('INSULT','–')} "
                  f"PROF={s['attribute_means'].get('PROFANITY','–')} "
                  f"ID={s['attribute_means'].get('IDENTITY_ATTACK','–')} "
                  f"THR={s['attribute_means'].get('THREAT','–')})")
            print(f"       Sample messages:")
            for m in s["top_messages"]:
                print(f"         [{m['toxicity']:.3f}] {m['user']}: {m['text']}")

    # Save
    out_path = root / "toxic_spans.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\n  → {out_path}")


if __name__ == "__main__":
    main()