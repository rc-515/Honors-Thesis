#!/usr/bin/env python3
"""
New User & Power User Profiles
================================
Reads scored_messages.csv + raw chat logs to compute:

1. NEW USER PROFILES (joined after first 25% of data):
   - Emote usage rate vs established users
   - Message frequency ramp-up
   - Toxicity on arrival vs later
   - How quickly they adopt emote culture
   - Category breakdown (text/emote/mixed)

2. POWER USER TOXICITY TYPOLOGY (top 50 by message count):
   - Dominant toxicity subtype per user
   - Aggregate: what % are insult-dominant vs profanity vs identity-attack
   - Emote rate among top users
   - Toxicity trajectory (early vs late)

Usage:
    python user_profiles.py --scored master_results/ --chat chat_logs/
"""

import csv
import json
import re
import sys
import argparse
import statistics
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime

EMOTE_RE = re.compile(r'\[emote:\d+:([^\]]+)\]')
EMOTE_TAG_RE = re.compile(r'\[emote:\d+:[^\]]+\]')
ATTRS = ["TOXICITY", "SEVERE_TOXICITY", "INSULT", "PROFANITY", "IDENTITY_ATTACK", "THREAT"]


def load_chat(folder):
    msgs = []
    for f in sorted(Path(folder).glob("*.json")):
        with open(f, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            raw = data if isinstance(data, list) else data.get("messages", data.get("data", []))
            msgs.extend(raw)
    msgs = [m for m in msgs if isinstance(m, dict) and m.get("createdAt")]
    msgs.sort(key=lambda m: m["createdAt"])
    return msgs


def load_scored(path):
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def categorize(content):
    stripped = EMOTE_TAG_RE.sub("", content).strip()
    has_emotes = bool(EMOTE_TAG_RE.search(content))
    if has_emotes and not stripped:
        return "emote_only"
    elif has_emotes:
        return "mixed"
    return "text_only"


def process_streamer(name, chat_folder, scored_path):
    print(f"\n{'='*55}")
    print(f"  {name}")
    print(f"{'='*55}")

    chat_msgs = load_chat(chat_folder)
    scored = load_scored(scored_path)
    print(f"  {len(chat_msgs):,} chat messages, {len(scored):,} scored")

    # Build scored lookup
    scored_lookup = {}
    for s in scored:
        key = (s.get("userId", ""), s.get("createdAt", ""))
        scores = {}
        for attr in ATTRS:
            try:
                scores[attr] = float(s[attr])
            except:
                scores[attr] = 0.0
        scored_lookup[key] = scores

    # ── Build per-user profiles from ALL chat messages ──
    user_data = defaultdict(lambda: {
        "msgs": [], "timestamps": [], "categories": Counter(),
        "emotes_used": Counter(), "scored_toxicity": [],
        "scored_attrs": defaultdict(list),
    })

    for msg in chat_msgs:
        uid = str(msg.get("userId", ""))
        ts = msg.get("createdAt", "")
        content = msg.get("content", "")
        cat = categorize(content)
        emotes = EMOTE_RE.findall(content)

        user_data[uid]["msgs"].append(ts)
        user_data[uid]["timestamps"].append(ts)
        user_data[uid]["categories"][cat] += 1
        for e in emotes:
            user_data[uid]["emotes_used"][e] += 1
        user_data[uid]["username"] = msg.get("username", uid)

        # Get toxicity if scored
        key = (uid, ts)
        if key in scored_lookup:
            scores = scored_lookup[key]
            user_data[uid]["scored_toxicity"].append(scores["TOXICITY"])
            for attr in ATTRS:
                user_data[uid]["scored_attrs"][attr].append(scores[attr])

    # ── Determine cutoff for "new" users ──
    all_ts = sorted(msg.get("createdAt", "") for msg in chat_msgs if msg.get("createdAt"))
    cutoff_50 = all_ts[len(all_ts) // 2]

    # Classify users
    new_users = []
    established_users = []
    all_user_profiles = []

    for uid, ud in user_data.items():
        if not ud["timestamps"]:
            continue

        first_ts = min(ud["timestamps"])
        last_ts = max(ud["timestamps"])
        total = len(ud["msgs"])
        cats = ud["categories"]

        profile = {
            "userId": uid,
            "username": ud["username"],
            "total_messages": total,
            "text_only": cats.get("text_only", 0),
            "emote_only": cats.get("emote_only", 0),
            "mixed": cats.get("mixed", 0),
            "emote_pct": round(cats.get("emote_only", 0) / total * 100, 1),
            "text_pct": round(cats.get("text_only", 0) / total * 100, 1),
            "unique_emotes": len(ud["emotes_used"]),
            "top_emotes": ud["emotes_used"].most_common(5),
            "first_seen": first_ts,
            "last_seen": last_ts,
            "is_new": first_ts > cutoff_50,
        }

        # Days active
        try:
            first_dt = datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
            last_dt = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
            days = max(1, (last_dt - first_dt).days + 1)
            unique_days = len(set(
                datetime.fromisoformat(t.replace("Z", "+00:00")).date()
                for t in ud["timestamps"]
            ))
            profile["days_span"] = days
            profile["days_active"] = unique_days
            profile["msgs_per_active_day"] = round(total / unique_days, 1)
        except:
            profile["days_span"] = 0
            profile["days_active"] = 0
            profile["msgs_per_active_day"] = 0

        # Toxicity stats if scored
        if ud["scored_toxicity"] and len(ud["scored_toxicity"]) >= 5:
            tox = ud["scored_toxicity"]
            profile["scored_messages"] = len(tox)
            profile["mean_toxicity"] = round(statistics.mean(tox), 4)

            # Early vs late
            split = len(tox) // 3
            if split >= 3:
                early = statistics.mean(tox[:split])
                late = statistics.mean(tox[-split:])
                profile["early_toxicity"] = round(early, 4)
                profile["late_toxicity"] = round(late, 4)
                profile["tox_delta_pct"] = round((late - early) / max(early, 0.001) * 100, 1)

            # Dominant subtype
            dominant = ""
            dominant_val = 0
            for attr in ATTRS:
                if attr == "TOXICITY" or attr == "SEVERE_TOXICITY":
                    continue
                vals = ud["scored_attrs"].get(attr, [])
                if vals:
                    m = statistics.mean(vals)
                    profile[f"mean_{attr}"] = round(m, 4)
                    if m > dominant_val:
                        dominant_val = m
                        dominant = attr
            profile["dominant_subtype"] = dominant

            # Emote evolution: early vs late emote rate
            sorted_msgs = sorted(zip(ud["timestamps"], 
                [categorize(msg.get("content","")) for msg in chat_msgs if str(msg.get("userId",""))==uid]),
                key=lambda x: x[0])
            if len(sorted_msgs) >= 20:
                third = len(sorted_msgs) // 3
                early_emote = sum(1 for _, c in sorted_msgs[:third] if c == "emote_only") / third * 100
                late_emote = sum(1 for _, c in sorted_msgs[-third:] if c == "emote_only") / third * 100
                profile["early_emote_pct"] = round(early_emote, 1)
                profile["late_emote_pct"] = round(late_emote, 1)
                profile["emote_adoption_delta"] = round(late_emote - early_emote, 1)

        all_user_profiles.append(profile)
        if profile["is_new"]:
            new_users.append(profile)
        else:
            established_users.append(profile)

    # ═══════════════════════════════════════════════════
    #  NEW USER ANALYSIS
    # ═══════════════════════════════════════════════════
    print(f"\n  NEW USERS (first seen after 25% mark): {len(new_users):,}")
    print(f"  Established users: {len(established_users):,}")

    def cohort_summary(users, label):
        if not users:
            return {"label": label, "n": 0}
        total_msgs = [u["total_messages"] for u in users]
        emote_pcts = [u["emote_pct"] for u in users]
        text_pcts = [u["text_pct"] for u in users]
        scored = [u for u in users if u.get("mean_toxicity") is not None]

        summary = {
            "label": label,
            "n_users": len(users),
            "total_messages": sum(total_msgs),
            "mean_msgs_per_user": round(statistics.mean(total_msgs), 1),
            "median_msgs_per_user": round(statistics.median(total_msgs), 1),
            "mean_emote_pct": round(statistics.mean(emote_pcts), 1),
            "median_emote_pct": round(statistics.median(emote_pcts), 1),
            "mean_text_pct": round(statistics.mean(text_pcts), 1),
            "mean_unique_emotes": round(statistics.mean(u["unique_emotes"] for u in users), 1),
        }

        if scored:
            summary["n_scored"] = len(scored)
            summary["mean_toxicity"] = round(statistics.mean(u["mean_toxicity"] for u in scored), 4)

            with_traj = [u for u in scored if "early_toxicity" in u]
            if with_traj:
                summary["mean_early_tox"] = round(statistics.mean(u["early_toxicity"] for u in with_traj), 4)
                summary["mean_late_tox"] = round(statistics.mean(u["late_toxicity"] for u in with_traj), 4)
                deltas = [u["tox_delta_pct"] for u in with_traj]
                summary["mean_tox_delta_pct"] = round(statistics.mean(deltas), 1)
                summary["pct_escalating"] = round(sum(1 for d in deltas if d > 5) / len(deltas) * 100, 1)
                summary["pct_deescalating"] = round(sum(1 for d in deltas if d < -5) / len(deltas) * 100, 1)

            with_emote_evol = [u for u in scored if "early_emote_pct" in u]
            if with_emote_evol:
                summary["mean_early_emote_pct"] = round(statistics.mean(u["early_emote_pct"] for u in with_emote_evol), 1)
                summary["mean_late_emote_pct"] = round(statistics.mean(u["late_emote_pct"] for u in with_emote_evol), 1)
                summary["mean_emote_adoption_delta"] = round(statistics.mean(u["emote_adoption_delta"] for u in with_emote_evol), 1)

            # Subtype breakdown
            subtypes = Counter(u.get("dominant_subtype", "") for u in scored if u.get("dominant_subtype"))
            if subtypes:
                summary["subtype_distribution"] = dict(subtypes.most_common())

        # Most active new users
        if label == "new_users":
            top_new = sorted(users, key=lambda u: u["total_messages"], reverse=True)[:15]
            summary["top_15"] = [{
                "username": u["username"],
                "total_messages": u["total_messages"],
                "emote_pct": u["emote_pct"],
                "days_active": u.get("days_active", 0),
                "mean_toxicity": u.get("mean_toxicity"),
                "dominant_subtype": u.get("dominant_subtype", ""),
            } for u in top_new]

        return summary

    new_summary = cohort_summary(new_users, "new_users")
    est_summary = cohort_summary(established_users, "established")

    # Print comparison
    print(f"\n  {'Metric':35s} {'New Users':>12s} {'Established':>12s}")
    print(f"  {'-'*62}")
    for key in ["n_users", "mean_msgs_per_user", "median_msgs_per_user",
                "mean_emote_pct", "median_emote_pct", "mean_unique_emotes",
                "mean_toxicity", "mean_early_tox", "mean_late_tox",
                "pct_escalating", "pct_deescalating",
                "mean_early_emote_pct", "mean_late_emote_pct", "mean_emote_adoption_delta"]:
        nv = new_summary.get(key, "–")
        ev = est_summary.get(key, "–")
        print(f"  {key:35s} {str(nv):>12s} {str(ev):>12s}")

    # ═══════════════════════════════════════════════════
    #  POWER USER TYPOLOGY
    # ═══════════════════════════════════════════════════
    print(f"\n  POWER USER TYPOLOGY (top 50 by message count):")

    top_users = sorted(all_user_profiles, key=lambda u: u["total_messages"], reverse=True)[:50]
    scored_top = [u for u in top_users if u.get("mean_toxicity") is not None]

    if scored_top:
        # Subtype distribution
        subtypes = Counter(u.get("dominant_subtype", "?") for u in scored_top)
        print(f"\n  Dominant subtype distribution among top 50:")
        for st, count in subtypes.most_common():
            pct = count / len(scored_top) * 100
            print(f"    {st:25s} {count:3d} ({pct:.0f}%)")

        # Top users table
        print(f"\n  {'Username':22s} {'Msgs':>7s} {'Emote%':>7s} {'Tox':>6s} {'Insult':>7s} {'Prof':>6s} {'IdAtk':>6s} {'Threat':>7s} {'Type':>15s}")
        print(f"  {'-'*90}")
        for u in scored_top[:25]:
            print(f"  {u['username'][:21]:22s} {u['total_messages']:7,d} {u['emote_pct']:6.1f}% "
                  f"{u.get('mean_toxicity',0):6.3f} {u.get('mean_INSULT',0):7.4f} "
                  f"{u.get('mean_PROFANITY',0):6.4f} {u.get('mean_IDENTITY_ATTACK',0):6.4f} "
                  f"{u.get('mean_THREAT',0):7.4f} {u.get('dominant_subtype','?'):>15s}")

        # Aggregate stats
        agg = {
            "n_top_users": len(scored_top),
            "mean_toxicity": round(statistics.mean(u["mean_toxicity"] for u in scored_top), 4),
            "mean_emote_pct": round(statistics.mean(u["emote_pct"] for u in scored_top), 1),
            "subtype_distribution": dict(subtypes.most_common()),
        }

        with_traj = [u for u in scored_top if "tox_delta_pct" in u]
        if with_traj:
            agg["pct_escalating"] = round(sum(1 for u in with_traj if u["tox_delta_pct"] > 5) / len(with_traj) * 100, 1)
            agg["pct_deescalating"] = round(sum(1 for u in with_traj if u["tox_delta_pct"] < -5) / len(with_traj) * 100, 1)
    else:
        agg = {"note": "No scored power users"}

    return {
        "streamer": name,
        "total_users": len(user_data),
        "new_user_summary": new_summary,
        "established_summary": est_summary,
        "power_user_typology": agg,
        "power_user_details": [{k: v for k, v in u.items() if k != "top_emotes"}
                               for u in (scored_top or top_users)[:50]],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scored", "-s", required=True, help="master_results/ directory")
    parser.add_argument("--chat", "-c", required=True, help="chat_logs/ directory")
    parser.add_argument("--output", "-o", default=None, help="Output dir (default: master_results/)")
    args = parser.parse_args()

    scored_dir = Path(args.scored)
    chat_dir = Path(args.chat)
    out = Path(args.output) if args.output else scored_dir

    print("=" * 60)
    print("  NEW USER & POWER USER PROFILES")
    print("=" * 60)

    all_results = {}

    for sdir in sorted(scored_dir.iterdir()):
        if not sdir.is_dir():
            continue
        name = sdir.name
        scored_path = sdir / "scored_messages.csv"
        chat_folder = chat_dir / name

        if not scored_path.exists():
            continue
        if not chat_folder.is_dir():
            print(f"\n  {name}: no chat folder at {chat_folder}, skipping")
            continue

        result = process_streamer(name, chat_folder, scored_path)
        all_results[name] = result

        out_path = sdir / "user_profiles.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\n  → {out_path}")

    # Cross-streamer new user comparison
    if len(all_results) > 1:
        print(f"\n{'='*60}")
        print(f"  CROSS-STREAMER NEW USER COMPARISON")
        print(f"{'='*60}")
        print(f"\n  {'Streamer':15s} {'New':>6s} {'Est':>6s} {'New Emote%':>11s} {'Est Emote%':>11s} {'New Tox':>8s} {'Est Tox':>8s} {'New Adopt Δ':>12s}")
        print(f"  {'-'*85}")
        for name, r in sorted(all_results.items()):
            ns = r["new_user_summary"]
            es = r["established_summary"]
            print(f"  {name:15s} {ns.get('n_users',0):6d} {es.get('n_users',0):6d} "
                  f"{ns.get('mean_emote_pct','–'):>11} {es.get('mean_emote_pct','–'):>11} "
                  f"{ns.get('mean_toxicity','–'):>8} {es.get('mean_toxicity','–'):>8} "
                  f"{ns.get('mean_emote_adoption_delta','–'):>12}")

        print(f"\n  CROSS-STREAMER POWER USER TYPOLOGY")
        print(f"  {'Streamer':15s} {'n':>4s} {'Mean Tox':>9s} {'Emote%':>8s} {'Insult':>8s} {'Prof':>8s} {'IdAtk':>8s} {'Threat':>8s}")
        print(f"  {'-'*70}")
        for name, r in sorted(all_results.items()):
            pu = r["power_user_typology"]
            details = r.get("power_user_details", [])
            if not details:
                continue
            scored_d = [d for d in details if d.get("mean_toxicity") is not None]
            if not scored_d:
                continue
            print(f"  {name:15s} {pu.get('n_top_users',0):4d} {pu.get('mean_toxicity',0):9.4f} "
                  f"{pu.get('mean_emote_pct',0):7.1f}% "
                  f"{statistics.mean(d.get('mean_INSULT',0) for d in scored_d):8.4f} "
                  f"{statistics.mean(d.get('mean_PROFANITY',0) for d in scored_d):8.4f} "
                  f"{statistics.mean(d.get('mean_IDENTITY_ATTACK',0) for d in scored_d):8.4f} "
                  f"{statistics.mean(d.get('mean_THREAT',0) for d in scored_d):8.4f}")

    combined_path = out / "user_profiles_combined.json"
    with open(combined_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\n  → {combined_path}")

    print(f"\n{'='*60}")
    print(f"  Done!")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
