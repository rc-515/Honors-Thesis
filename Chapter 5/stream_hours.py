#!/usr/bin/env python3
"""
Stream Hours Calculator
========================
Estimates total hours of footage per streamer by measuring the
time between first and last message in each JSON file.

Usage:
    python stream_hours.py --input chat_logs/
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime


def parse_ts(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def calc_folder(folder):
    streams = []
    for f in sorted(folder.glob("*.json")):
        with open(f, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            msgs = data if isinstance(data, list) else data.get("messages", data.get("data", []))
            msgs = [m for m in msgs if isinstance(m, dict) and m.get("createdAt")]
        if len(msgs) < 2:
            continue
        msgs.sort(key=lambda m: m["createdAt"])
        first = parse_ts(msgs[0]["createdAt"])
        last = parse_ts(msgs[-1]["createdAt"])
        dur = (last - first).total_seconds()
        streams.append({
            "file": f.name,
            "date": first.strftime("%Y-%m-%d"),
            "start": first.strftime("%H:%M"),
            "end": last.strftime("%H:%M"),
            "hours": round(dur / 3600, 2),
            "messages": len(msgs),
        })
    return streams


def main():
    parser = argparse.ArgumentParser(description="Calculate total stream hours")
    parser.add_argument("--input", "-i", required=True)
    args = parser.parse_args()

    root = Path(args.input)
    folders = [d for d in sorted(root.iterdir()) if d.is_dir() and list(d.glob("*.json"))]
    if not folders:
        folders = [root]

    grand_total = 0

    for folder in folders:
        name = folder.name
        streams = calc_folder(folder)
        if not streams:
            continue

        total_h = sum(s["hours"] for s in streams)
        total_msgs = sum(s["messages"] for s in streams)
        grand_total += total_h

        print(f"\n{'='*65}")
        print(f"  {name}: {len(streams)} streams, {total_h:.1f} hours, {total_msgs:,} messages")
        print(f"{'='*65}")
        print(f"  {'Date':12s} {'Start':>6s} {'End':>6s} {'Hours':>6s} {'Msgs':>8s}")
        print(f"  {'-'*42}")
        for s in streams:
            print(f"  {s['date']:12s} {s['start']:>6s} {s['end']:>6s} {s['hours']:6.1f} {s['messages']:8,d}")

    print(f"\n{'='*65}")
    print(f"  GRAND TOTAL: {grand_total:.1f} hours across all streamers")
    print(f"{'='*65}")


if __name__ == "__main__":
    main()
