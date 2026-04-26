#!/usr/bin/env python3
"""
Master Multi-Streamer Toxicity Pipeline
=========================================
Processes ALL subfolders in chat_logs/, scores EVERY text message
with Detoxify, and produces per-streamer + combined analyses.

Structure expected:
    chat_logs/
        streamer_a/
            stream1.json
            stream2.json
        streamer_b/
            ...

Install:
    pip install detoxify pandas scipy

Usage:
    python master_pipeline.py --input chat_logs/ --output master_results/

    Score every single message (can take a while but Detoxify is fast):
    python master_pipeline.py --input chat_logs/ --output master_results/ --score-all

Analyses produced:
    1. Per-streamer toxicity profiles (all 6 attributes)
    2. Cross-streamer comparison
    3. Multi-attribute breakdown (who's insulting vs profane vs threatening?)
    4. Toxicity contagion (does a toxic msg trigger more toxic follow-ups?)
    5. Temporal patterns (toxicity by hour, by day)
    6. First-message analysis (how toxic are people's very first messages?)
    7. Toxicity burst detection
    8. Per-user attribute profiles
"""

import json
import csv
import sys
import re
import os
import time
import argparse
import statistics
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime

try:
    from detoxify import Detoxify
except ImportError:
    print("ERROR: pip install detoxify")
    sys.exit(1)

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

try:
    from scipy import stats as sp
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

EMOTE_RE = re.compile(r'\[emote:\d+:[^\]]+\]')
ATTRS = ["toxicity", "severe_toxicity", "insult", "obscene", "identity_attack", "threat"]
ATTR_LABELS = {"toxicity":"TOXICITY","severe_toxicity":"SEVERE_TOXICITY","insult":"INSULT",
               "obscene":"PROFANITY","identity_attack":"IDENTITY_ATTACK","threat":"THREAT"}


# ═══════════════════════════════════════════════════════════════
#  LOADING
# ═══════════════════════════════════════════════════════════════

def load_streamer_folder(folder: Path) -> list[dict]:
    msgs = []
    for f in sorted(folder.glob("*.json")):
        with open(f, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            raw = data if isinstance(data, list) else data.get("messages", data.get("data", []))
            msgs.extend(raw)
    msgs = [m for m in msgs if isinstance(m, dict) and m.get("createdAt")]
    msgs.sort(key=lambda m: m["createdAt"])
    return msgs


def discover_streamers(input_dir: Path) -> dict:
    """Find all streamer subfolders, or treat input_dir as a single streamer."""
    streamers = {}
    subdirs = [d for d in sorted(input_dir.iterdir()) if d.is_dir()]
    if subdirs:
        for d in subdirs:
            jsons = list(d.glob("*.json"))
            if jsons:
                streamers[d.name] = d
    else:
        jsons = list(input_dir.glob("*.json"))
        if jsons:
            streamers[input_dir.name] = input_dir
    return streamers


def categorize(content: str):
    stripped = EMOTE_RE.sub("", content).strip()
    has_emotes = bool(EMOTE_RE.search(content))
    if has_emotes and not stripped:
        return "emote_only", ""
    elif has_emotes:
        return "mixed", stripped
    return "text_only", stripped


# ═══════════════════════════════════════════════════════════════
#  SCORING
# ═══════════════════════════════════════════════════════════════

def score_messages(messages: list[dict], model, batch_size=128,
                   score_all=False, top_n_users=200, min_text=10):
    """Score messages with Detoxify. Returns list of enriched message dicts."""

    # Enrich messages
    user_counter = defaultdict(int)
    scoreable = []
    for msg in messages:
        uid = str(msg.get("userId", ""))
        content = msg.get("content", "")
        cat, clean = categorize(content)
        user_counter[uid] += 1
        msg["_cat"] = cat
        msg["_clean"] = clean
        msg["_uidx"] = user_counter[uid]
        if cat in ("text_only", "mixed") and len(clean) >= 3:
            scoreable.append(msg)

    # Select which messages to score
    if not score_all:
        # Pick top N users by total messages who have enough text
        user_text_counts = Counter()
        for m in scoreable:
            user_text_counts[str(m.get("userId", ""))] += 1
        user_total = Counter(str(m.get("userId","")) for m in messages)
        candidates = [(uid, user_total[uid]) for uid, tc in user_text_counts.items() if tc >= min_text]
        candidates.sort(key=lambda x: x[1], reverse=True)
        keep_uids = set(uid for uid, _ in candidates[:top_n_users])
        scoreable = [m for m in scoreable if str(m.get("userId","")) in keep_uids]

    if not scoreable:
        return []

    print(f"    Scoring {len(scoreable):,} messages...")
    results = []
    start = time.time()

    for i in range(0, len(scoreable), batch_size):
        batch = scoreable[i:i+batch_size]
        texts = [m["_clean"] for m in batch]
        scores = model.predict(texts)

        for j, msg in enumerate(batch):
            row = {
                "username": msg.get("username", ""),
                "userId": str(msg.get("userId", "")),
                "createdAt": msg.get("createdAt", ""),
                "content": msg.get("content", ""),
                "clean_text": msg["_clean"],
                "category": msg["_cat"],
                "user_msg_index": msg["_uidx"],
            }
            for attr in ATTRS:
                row[ATTR_LABELS.get(attr, attr)] = scores[attr][j]
            results.append(row)

        done = min(i + batch_size, len(scoreable))
        if done % (batch_size * 20) == 0 or done >= len(scoreable):
            elapsed = time.time() - start
            rate = done / elapsed if elapsed > 0 else 0
            print(f"      {done:,}/{len(scoreable):,} ({rate:.0f}/sec)")

    print(f"    Done: {len(results):,} scored in {time.time()-start:.1f}s")
    return results


# ═══════════════════════════════════════════════════════════════
#  ANALYSIS FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def basic_stats(scored: list[dict]) -> dict:
    """Global stats across all scored messages."""
    if not scored:
        return {}
    stats = {"n_messages": len(scored), "n_users": len(set(r["userId"] for r in scored))}
    for attr_label in ATTR_LABELS.values():
        vals = [r[attr_label] for r in scored if attr_label in r]
        if vals:
            stats[attr_label] = {
                "mean": round(statistics.mean(vals), 4),
                "median": round(statistics.median(vals), 4),
                "std": round(statistics.stdev(vals), 4) if len(vals) > 1 else 0,
                "pct_above_05": round(sum(1 for v in vals if v > 0.5) / len(vals) * 100, 2),
                "pct_above_07": round(sum(1 for v in vals if v > 0.7) / len(vals) * 100, 2),
            }
    return stats


def multi_attribute_profiles(scored: list[dict], top_n=50) -> list[dict]:
    """Per-user profiles across all 6 attributes — who's insulting vs profane vs threatening?"""
    user_scores = defaultdict(lambda: defaultdict(list))
    user_names = {}
    for r in scored:
        uid = r["userId"]
        user_names[uid] = r["username"]
        for attr in ATTR_LABELS.values():
            if attr in r:
                user_scores[uid][attr].append(r[attr])

    profiles = []
    for uid, attrs in user_scores.items():
        if len(attrs.get("TOXICITY", [])) < 10:
            continue
        profile = {"userId": uid, "username": user_names[uid],
                   "n_scored": len(attrs.get("TOXICITY", []))}
        dominant_attr = ""
        dominant_val = 0
        for attr, vals in attrs.items():
            m = statistics.mean(vals)
            profile[f"mean_{attr}"] = round(m, 4)
            profile[f"pct_above_05_{attr}"] = round(sum(1 for v in vals if v > 0.5)/len(vals)*100, 1)
            if attr != "TOXICITY" and m > dominant_val:
                dominant_val = m
                dominant_attr = attr
        profile["dominant_subtype"] = dominant_attr
        profiles.append(profile)

    profiles.sort(key=lambda p: p.get("mean_TOXICITY", 0), reverse=True)
    return profiles[:top_n]


def contagion_analysis(scored: list[dict], window=5, threshold=0.5) -> dict:
    """Does a toxic message increase toxicity of the next N messages?"""
    if len(scored) < window * 2:
        return {"note": "Too few messages for contagion analysis"}

    # Sort by timestamp
    sorted_msgs = sorted(scored, key=lambda m: m["createdAt"])
    tox = [m["TOXICITY"] for m in sorted_msgs]

    after_toxic = []
    after_clean = []

    for i, score in enumerate(tox):
        if i + window >= len(tox):
            break
        following = tox[i+1:i+1+window]
        avg_following = statistics.mean(following)
        if score >= threshold:
            after_toxic.append(avg_following)
        elif score < 0.1:
            after_clean.append(avg_following)

    result = {
        "threshold": threshold,
        "window": window,
        "n_toxic_triggers": len(after_toxic),
        "n_clean_triggers": len(after_clean),
    }

    if after_toxic and after_clean:
        result["mean_tox_after_toxic_msg"] = round(statistics.mean(after_toxic), 4)
        result["mean_tox_after_clean_msg"] = round(statistics.mean(after_clean), 4)
        result["contagion_ratio"] = round(
            statistics.mean(after_toxic) / max(statistics.mean(after_clean), 0.0001), 2)

        if HAS_SCIPY and len(after_toxic) >= 5 and len(after_clean) >= 5:
            stat, pval = sp.mannwhitneyu(after_toxic, after_clean, alternative='greater')
            result["mann_whitney_p"] = round(pval, 6)
            result["significant_p05"] = pval < 0.05

    return result


def temporal_analysis(scored: list[dict]) -> dict:
    """Toxicity by hour of day and day of week."""
    hourly = defaultdict(list)
    daily = defaultdict(list)

    for m in scored:
        try:
            dt = datetime.fromisoformat(m["createdAt"].replace("Z", "+00:00"))
            hourly[dt.hour].append(m["TOXICITY"])
            daily[dt.strftime("%A")].append(m["TOXICITY"])
        except:
            pass

    hour_stats = {h: {"mean": round(statistics.mean(v), 4), "n": len(v)}
                  for h, v in sorted(hourly.items())}
    day_stats = {d: {"mean": round(statistics.mean(v), 4), "n": len(v)}
                 for d, v in daily.items()}

    return {"by_hour": hour_stats, "by_day": day_stats}


def first_message_analysis(scored: list[dict]) -> dict:
    """How toxic are NEW users' very first messages vs their overall average?
    Only includes users whose first message appeared after the first 25% of
    the data's time range — i.e., genuinely new arrivals, not existing users
    whose first captured message is an artifact of when data collection began."""

    if not scored:
        return {}

    # Find the global time range
    timestamps = []
    for m in scored:
        ts = m.get("createdAt", "")
        if ts:
            timestamps.append(ts)
    if not timestamps:
        return {}

    timestamps.sort()
    global_start = timestamps[0]
    global_end = timestamps[-1]

    # Cutoff: users must have first appeared after the first 25% of the period
    # Use string comparison since ISO timestamps sort correctly
    n_ts = len(timestamps)
    cutoff_idx = n_ts // 4
    cutoff_ts = timestamps[cutoff_idx]

    # Group messages by user
    user_msgs = defaultdict(list)
    for m in scored:
        user_msgs[m["userId"]].append(m)

    first_tox = []
    overall_tox = []
    n_excluded = 0

    for uid, msgs in user_msgs.items():
        msgs.sort(key=lambda m: m.get("createdAt", ""))
        if len(msgs) < 5:
            continue

        # Only include users whose first message is after the cutoff
        first_ts = msgs[0].get("createdAt", "")
        if first_ts <= cutoff_ts:
            n_excluded += 1
            continue

        first_tox.append(msgs[0]["TOXICITY"])
        overall_tox.append(statistics.mean(m["TOXICITY"] for m in msgs))

    if not first_tox:
        return {"note": "No new users with 5+ scored messages found after 25% cutoff",
                "n_excluded_existing": n_excluded}

    return {
        "n_new_users": len(first_tox),
        "n_excluded_existing": n_excluded,
        "mean_first_message_toxicity": round(statistics.mean(first_tox), 4),
        "mean_overall_toxicity": round(statistics.mean(overall_tox), 4),
        "first_vs_overall_delta": round(
            statistics.mean(first_tox) - statistics.mean(overall_tox), 4),
        "pct_first_msg_above_05": round(
            sum(1 for v in first_tox if v > 0.5) / len(first_tox) * 100, 1),
        "pct_overall_above_05": round(
            sum(1 for v in overall_tox if v > 0.5) / len(overall_tox) * 100, 1),
    }


def burst_detection(scored: list[dict], window=20, threshold=0.3) -> list[dict]:
    """Find temporal windows where mean toxicity spikes."""
    sorted_msgs = sorted(scored, key=lambda m: m["createdAt"])
    bursts = []

    for i in range(0, len(sorted_msgs) - window, window // 2):
        chunk = sorted_msgs[i:i+window]
        mean_tox = statistics.mean(m["TOXICITY"] for m in chunk)
        if mean_tox >= threshold:
            bursts.append({
                "start": chunk[0]["createdAt"],
                "end": chunk[-1]["createdAt"],
                "mean_toxicity": round(mean_tox, 4),
                "n_messages": len(chunk),
                "n_unique_users": len(set(m["userId"] for m in chunk)),
                "top_message": max(chunk, key=lambda m: m["TOXICITY"])["clean_text"][:100],
            })

    bursts.sort(key=lambda b: b["mean_toxicity"], reverse=True)
    return bursts[:20]


# ═══════════════════════════════════════════════════════════════
#  MAIN PIPELINE
# ═══════════════════════════════════════════════════════════════

def process_streamer(name: str, folder: Path, model, out_dir: Path,
                     score_all=False, top_n_users=200, batch_size=128):
    """Run full analysis for one streamer."""
    print(f"\n{'='*60}")
    print(f"  STREAMER: {name}")
    print(f"{'='*60}")

    sdir = out_dir / name
    sdir.mkdir(parents=True, exist_ok=True)

    # Load
    print("  Loading messages...")
    messages = load_streamer_folder(folder)
    print(f"  {len(messages):,} messages loaded")

    if not messages:
        print("  [SKIP] No messages found")
        return None

    # Categorize
    cats = Counter()
    for m in messages:
        cat, _ = categorize(m.get("content", ""))
        cats[cat] += 1

    n_users = len(set(str(m.get("userId","")) for m in messages))
    print(f"  {n_users:,} users | text:{cats['text_only']:,} emote:{cats['emote_only']:,} mixed:{cats['mixed']:,}")

    # Score
    print("  Scoring...")
    scored = score_messages(messages, model, batch_size=batch_size,
                            score_all=score_all, top_n_users=top_n_users)

    if not scored:
        print("  [SKIP] No scoreable messages")
        return None

    # Run analyses
    print("  Analyzing...")
    stats = basic_stats(scored)
    attr_profiles = multi_attribute_profiles(scored)
    contagion = contagion_analysis(scored)
    temporal = temporal_analysis(scored)
    first_msg = first_message_analysis(scored)
    bursts = burst_detection(scored)

    # Export scored CSV
    csv_path = sdir / "scored_messages.csv"
    if scored:
        keys = list(scored[0].keys())
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            for r in scored:
                w.writerow(r)

    # Export analyses
    results = {
        "streamer": name,
        "total_messages": len(messages),
        "total_users": n_users,
        "category_breakdown": dict(cats),
        "scored_messages": len(scored),
        "scored_users": stats.get("n_users", 0),
        "attribute_stats": {k: v for k, v in stats.items() if isinstance(v, dict)},
        "contagion": contagion,
        "temporal": temporal,
        "first_message": first_msg,
        "top_toxic_bursts": bursts[:5],
        "top_attribute_profiles": attr_profiles[:20],
    }

    with open(sdir / "analysis.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"  Results → {sdir}/")
    return results


def cross_streamer_comparison(all_results: dict, out_dir: Path):
    """Compare toxicity metrics across streamers."""
    print(f"\n{'='*60}")
    print(f"  CROSS-STREAMER COMPARISON")
    print(f"{'='*60}")

    comparison = []
    for name, r in all_results.items():
        if not r:
            continue
        entry = {
            "streamer": name,
            "total_messages": r["total_messages"],
            "total_users": r["total_users"],
            "scored_messages": r["scored_messages"],
            "emote_pct": round(r["category_breakdown"].get("emote_only", 0) / max(r["total_messages"], 1) * 100, 1),
        }
        for attr in ATTR_LABELS.values():
            astats = r.get("attribute_stats", {}).get(attr, {})
            entry[f"{attr}_mean"] = astats.get("mean", 0)
            entry[f"{attr}_pct_above_07"] = astats.get("pct_above_07", 0)

        cg = r.get("contagion", {})
        entry["contagion_ratio"] = cg.get("contagion_ratio", 0)
        entry["contagion_significant"] = cg.get("significant_p05", False)

        comparison.append(entry)

    # Sort by toxicity
    comparison.sort(key=lambda c: c.get("TOXICITY_mean", 0), reverse=True)

    # Print
    print(f"\n  {'Streamer':25s} {'Msgs':>8s} {'Users':>7s} {'Tox Mean':>9s} {'Insult':>8s} {'Profane':>8s} {'IdAtk':>8s} {'Threat':>8s} {'Contag':>7s}")
    print("  " + "-" * 100)
    for c in comparison:
        print(f"  {c['streamer']:25s} {c['total_messages']:8,d} {c['total_users']:7,d} "
              f"{c.get('TOXICITY_mean',0):9.4f} {c.get('INSULT_mean',0):8.4f} "
              f"{c.get('PROFANITY_mean',0):8.4f} {c.get('IDENTITY_ATTACK_mean',0):8.4f} "
              f"{c.get('THREAT_mean',0):8.4f} {c.get('contagion_ratio',0):7.2f}")

    with open(out_dir / "cross_streamer_comparison.json", "w", encoding="utf-8") as f:
        json.dump(comparison, f, indent=2)

    # CSV version
    if comparison:
        with open(out_dir / "cross_streamer_comparison.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(comparison[0].keys()))
            w.writeheader()
            for row in comparison:
                w.writerow(row)

    print(f"\n  → {out_dir}/cross_streamer_comparison.json")
    return comparison


def main():
    parser = argparse.ArgumentParser(description="Master multi-streamer toxicity pipeline")
    parser.add_argument("--input", "-i", required=True, help="chat_logs/ directory with streamer subfolders")
    parser.add_argument("--output", "-o", default="master_results", help="Output directory")
    parser.add_argument("--model", default="unbiased", choices=["original","unbiased","original-small","unbiased-small"])
    parser.add_argument("--score-all", action="store_true", help="Score ALL text messages (slower but comprehensive)")
    parser.add_argument("--top-users", type=int, default=200, help="Per-streamer: score top N users (default 200, ignored if --score-all)")
    parser.add_argument("--batch-size", type=int, default=128, help="Detoxify batch size")

    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("  MASTER MULTI-STREAMER TOXICITY PIPELINE")
    print(f"  Model: Detoxify ({args.model})")
    print(f"  Mode: {'ALL messages' if args.score_all else f'Top {args.top_users} users per streamer'}")
    print("=" * 60)

    # Discover streamers
    input_dir = Path(args.input)
    streamers = discover_streamers(input_dir)
    print(f"\n  Found {len(streamers)} streamer(s): {', '.join(streamers.keys())}")

    # Load model once
    print(f"\n  Loading Detoxify model '{args.model}'...")
    model = Detoxify(args.model)
    print("  Model ready!")

    # Process each streamer
    all_results = {}
    for name, folder in streamers.items():
        result = process_streamer(
            name, folder, model, out,
            score_all=args.score_all,
            top_n_users=args.top_users,
            batch_size=args.batch_size,
        )
        all_results[name] = result

    # Cross-streamer comparison
    if len(all_results) > 1:
        cross_streamer_comparison(all_results, out)

    # Combined summary
    combined = {
        "streamers_analyzed": len(all_results),
        "total_messages_all": sum(r["total_messages"] for r in all_results.values() if r),
        "total_scored_all": sum(r["scored_messages"] for r in all_results.values() if r),
        "per_streamer": {k: {
            "messages": v["total_messages"],
            "users": v["total_users"],
            "scored": v["scored_messages"],
            "mean_toxicity": v["attribute_stats"].get("TOXICITY", {}).get("mean", 0),
            "mean_insult": v["attribute_stats"].get("INSULT", {}).get("mean", 0),
            "mean_profanity": v["attribute_stats"].get("PROFANITY", {}).get("mean", 0),
            "mean_identity_attack": v["attribute_stats"].get("IDENTITY_ATTACK", {}).get("mean", 0),
            "mean_threat": v["attribute_stats"].get("THREAT", {}).get("mean", 0),
            "contagion_ratio": v.get("contagion", {}).get("contagion_ratio", 0),
        } for k, v in all_results.items() if v},
    }
    with open(out / "combined_summary.json", "w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2)

    print(f"\n{'='*60}")
    print(f"  ALL DONE — results in {out}/")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()