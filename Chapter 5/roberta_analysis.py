#!/usr/bin/env python3
"""
RoBERTa Hate Speech Analysis: New Users + Viewership
======================================================
Uses your roberta_results/ scored CSVs to test:
  1. Do new users have lower hate speech than established users?
  2. Are new users' FIRST messages less hateful than their average?
  3. Does hate speech increase with viewership?

Usage:
    python roberta_analysis.py \
        --roberta roberta_results/ \
        --chat chat_logs/ \
        --viewership viewership_results/ \
        --output roberta_analysis/
"""

import csv
import json
import sys
import argparse
import statistics
from pathlib import Path
from collections import defaultdict
from datetime import datetime

try:
    from scipy import stats as sp
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


def load_csv(path):
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


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


def find_score_column(row):
    """Auto-detect the hate speech score column name."""
    candidates = [
        "roberta-hate-speech-dynabench-r4-target_score",
        "dynabench_score", "hate_score", "TOXICITY",
    ]
    for c in candidates:
        if c in row:
            return c
    # Try any column ending in _score
    for k in row:
        if k.endswith("_SCORE"):
            return k
    return None


def process_streamer(name, roberta_path, chat_folder, viewership_dir, out_dir):
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")

    scored = load_csv(roberta_path)
    if not scored:
        print("  No scored data")
        return None

    # Auto-detect score column
    score_col = find_score_column(scored[0])
    if not score_col:
        print(f"  Could not find score column. Available: {list(scored[0].keys())}")
        return None
    print(f"  Score column: {score_col}")
    print(f"  {len(scored):,} scored messages")

    # Parse scores
    for r in scored:
        try:
            r["_hate"] = float(r[score_col])
        except:
            r["_hate"] = None

    scored = [r for r in scored if r["_hate"] is not None]
    print(f"  {len(scored):,} with valid scores")

    # Global stats
    all_hate = [r["_hate"] for r in scored]
    print(f"  Global hate: mean={statistics.mean(all_hate):.4f}, "
          f"median={statistics.median(all_hate):.4f}, "
          f">0.5={sum(1 for h in all_hate if h > 0.5)/len(all_hate)*100:.1f}%")

    # Load chat to find new users
    chat_msgs = load_chat(chat_folder) if chat_folder.is_dir() else []
    print(f"  {len(chat_msgs):,} raw chat messages")

    # ═══════════════════════════════════════════════════════════
    #  1. NEW USER vs ESTABLISHED HATE SPEECH
    # ═══════════════════════════════════════════════════════════
    print(f"\n  [1] NEW USER vs ESTABLISHED HATE SPEECH")

    # Find first-seen timestamp per user from raw chat
    user_first_seen = {}
    for m in chat_msgs:
        uid = str(m.get("userId", ""))
        ts = m.get("createdAt", "")
        if uid and ts:
            if uid not in user_first_seen or ts < user_first_seen[uid]:
                user_first_seen[uid] = ts

    # If no chat data, use scored messages
    if not user_first_seen:
        for r in scored:
            uid = str(r.get("userId", ""))
            ts = r.get("createdAt", "")
            if uid and ts:
                if uid not in user_first_seen or ts < user_first_seen[uid]:
                    user_first_seen[uid] = ts

    # Cutoff at 25%
    all_ts = sorted(user_first_seen.values())
    if not all_ts:
        print("  No timestamp data")
        return None
    cutoff = all_ts[len(all_ts) // 2]

    new_uids = set(uid for uid, ts in user_first_seen.items() if ts > cutoff)
    est_uids = set(uid for uid, ts in user_first_seen.items() if ts <= cutoff)

    # Group scored messages
    new_scores = [r["_hate"] for r in scored if str(r.get("userId", "")) in new_uids]
    est_scores = [r["_hate"] for r in scored if str(r.get("userId", "")) in est_uids]

    new_vs_est = {
        "n_new_msgs": len(new_scores),
        "n_est_msgs": len(est_scores),
        "n_new_users": len(new_uids),
        "n_est_users": len(est_uids),
    }

    if new_scores and est_scores:
        new_mean = statistics.mean(new_scores)
        est_mean = statistics.mean(est_scores)
        new_vs_est["new_mean_hate"] = round(new_mean, 4)
        new_vs_est["est_mean_hate"] = round(est_mean, 4)
        new_vs_est["delta"] = round(new_mean - est_mean, 4)
        new_vs_est["new_pct_above_05"] = round(
            sum(1 for s in new_scores if s > 0.5) / len(new_scores) * 100, 2)
        new_vs_est["est_pct_above_05"] = round(
            sum(1 for s in est_scores if s > 0.5) / len(est_scores) * 100, 2)

        if HAS_SCIPY:
            stat, pval = sp.mannwhitneyu(new_scores, est_scores, alternative='two-sided')
            new_vs_est["mann_whitney_p"] = round(pval, 8)
            new_vs_est["significant"] = pval < 0.05

        print(f"    New users:   mean={new_mean:.4f}  >0.5={new_vs_est['new_pct_above_05']:.1f}%  "
              f"(n={len(new_scores):,} msgs, {len(new_uids):,} users)")
        print(f"    Established: mean={est_mean:.4f}  >0.5={new_vs_est['est_pct_above_05']:.1f}%  "
              f"(n={len(est_scores):,} msgs, {len(est_uids):,} users)")
        print(f"    Delta: {new_vs_est['delta']:+.4f}  "
              f"{'NEW LOWER' if new_mean < est_mean else 'NEW HIGHER'}")
        if "mann_whitney_p" in new_vs_est:
            print(f"    Mann-Whitney p={new_vs_est['mann_whitney_p']:.8f}  "
                  f"{'*** SIGNIFICANT ***' if new_vs_est['significant'] else 'not significant'}")

    # Per-user means comparison
    user_hate = defaultdict(list)
    for r in scored:
        uid = str(r.get("userId", ""))
        user_hate[uid].append(r["_hate"])

    new_user_means = [statistics.mean(v) for uid, v in user_hate.items()
                      if uid in new_uids and len(v) >= 5]
    est_user_means = [statistics.mean(v) for uid, v in user_hate.items()
                      if uid in est_uids and len(v) >= 5]

    per_user = {}
    if new_user_means and est_user_means:
        per_user["n_new"] = len(new_user_means)
        per_user["n_est"] = len(est_user_means)
        per_user["new_mean_of_means"] = round(statistics.mean(new_user_means), 4)
        per_user["est_mean_of_means"] = round(statistics.mean(est_user_means), 4)
        per_user["delta"] = round(
            statistics.mean(new_user_means) - statistics.mean(est_user_means), 4)

        if HAS_SCIPY:
            stat, pval = sp.mannwhitneyu(new_user_means, est_user_means, alternative='two-sided')
            per_user["mann_whitney_p"] = round(pval, 8)
            per_user["significant"] = pval < 0.05

        print(f"\n    Per-user means (≥5 msgs):")
        print(f"    New users:   mean of means={per_user['new_mean_of_means']:.4f} (n={per_user['n_new']})")
        print(f"    Established: mean of means={per_user['est_mean_of_means']:.4f} (n={per_user['n_est']})")
        if "mann_whitney_p" in per_user:
            print(f"    p={per_user['mann_whitney_p']:.8f}  "
                  f"{'*** SIGNIFICANT ***' if per_user['significant'] else 'not significant'}")

    # ═══════════════════════════════════════════════════════════
    #  2. FIRST MESSAGE HATE SPEECH (new users only)
    # ═══════════════════════════════════════════════════════════
    print(f"\n  [2] FIRST MESSAGE HATE SPEECH (new users only)")

    user_scored_msgs = defaultdict(list)
    for r in scored:
        uid = str(r.get("userId", ""))
        if uid in new_uids:
            user_scored_msgs[uid].append(r)

    first_msg_hate = []
    overall_hate = []
    for uid, msgs in user_scored_msgs.items():
        msgs.sort(key=lambda m: m.get("createdAt", ""))
        if len(msgs) < 5:
            continue
        first_msg_hate.append(msgs[0]["_hate"])
        overall_hate.append(statistics.mean(m["_hate"] for m in msgs))

    first_msg = {}
    if first_msg_hate:
        fm_mean = statistics.mean(first_msg_hate)
        ov_mean = statistics.mean(overall_hate)
        first_msg["n_new_users"] = len(first_msg_hate)
        first_msg["first_msg_mean_hate"] = round(fm_mean, 4)
        first_msg["overall_mean_hate"] = round(ov_mean, 4)
        first_msg["delta"] = round(fm_mean - ov_mean, 4)
        first_msg["first_msg_pct_above_05"] = round(
            sum(1 for h in first_msg_hate if h > 0.5) / len(first_msg_hate) * 100, 1)

        print(f"    New users with ≥5 scored msgs: {len(first_msg_hate)}")
        print(f"    First message hate: {fm_mean:.4f}")
        print(f"    Overall mean hate:  {ov_mean:.4f}")
        print(f"    Delta: {first_msg['delta']:+.4f}  "
              f"{'first msg LOWER' if fm_mean < ov_mean else 'first msg HIGHER'}")
        print(f"    First msg >0.5: {first_msg['first_msg_pct_above_05']:.1f}%")

        # Trajectory: early vs late hate
        early_hate = []
        late_hate = []
        for uid, msgs in user_scored_msgs.items():
            msgs.sort(key=lambda m: m.get("createdAt", ""))
            if len(msgs) < 9:
                continue
            split = len(msgs) // 3
            early_hate.append(statistics.mean(m["_hate"] for m in msgs[:split]))
            late_hate.append(statistics.mean(m["_hate"] for m in msgs[-split:]))

        if early_hate:
            em = statistics.mean(early_hate)
            lm = statistics.mean(late_hate)
            first_msg["early_mean"] = round(em, 4)
            first_msg["late_mean"] = round(lm, 4)
            first_msg["early_vs_late_delta"] = round(lm - em, 4)
            print(f"    Early-third hate: {em:.4f} → Late-third: {lm:.4f} "
                  f"(Δ={lm-em:+.4f})")
    else:
        print("    No new users with ≥5 scored messages")

    # ═══════════════════════════════════════════════════════════
    #  3. HATE SPEECH vs VIEWERSHIP
    # ═══════════════════════════════════════════════════════════
    print(f"\n  [3] HATE SPEECH vs VIEWERSHIP")

    viewership_result = {}
    vdir = viewership_dir / name if viewership_dir else None
    wpath = vdir / "windowed_data.csv" if vdir and vdir.is_dir() else None

    if wpath and wpath.exists():
        windows = load_csv(wpath)
        print(f"    {len(windows):,} viewership windows")

        # Build lookup: 5-min bin -> viewer count
        viewer_bins = {}
        for w in windows:
            dt_str = w.get("datetime", "")
            try:
                dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00")).replace(tzinfo=None)
                epoch = int(dt.timestamp())
                key = epoch - (epoch % 300)
                viewers = int(w.get("viewers", 0))
                if viewers > 0:
                    viewer_bins[key] = viewers
            except:
                continue

        # Bin scored messages into 5-min windows
        window_hate = defaultdict(list)
        matched = 0
        for r in scored:
            ts = r.get("createdAt", "")
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
                epoch = int(dt.timestamp())
                key = epoch - (epoch % 300)
                if key in viewer_bins:
                    window_hate[key].append(r["_hate"])
                    matched += 1
                elif key - 300 in viewer_bins:
                    window_hate[key - 300].append(r["_hate"])
                    matched += 1
                elif key + 300 in viewer_bins:
                    window_hate[key + 300].append(r["_hate"])
                    matched += 1
            except:
                continue

        print(f"    {matched:,} scored messages matched to windows")

        # Compute per-window mean hate + viewer count
        pairs = []
        for key, hates in window_hate.items():
            viewers = viewer_bins.get(key)
            if viewers and viewers > 100 and hates:
                pairs.append((viewers, statistics.mean(hates)))

        print(f"    {len(pairs):,} windows with both data")

        if len(pairs) >= 20 and HAS_SCIPY:
            viewers, hates = zip(*pairs)
            pr, pp = sp.pearsonr(viewers, hates)
            sr, spp = sp.spearmanr(viewers, hates)

            viewership_result = {
                "n_windows": len(pairs),
                "pearson_r": round(pr, 4),
                "pearson_p": round(pp, 6),
                "spearman_r": round(sr, 4),
                "spearman_p": round(spp, 6),
                "significant": pp < 0.05 or spp < 0.05,
            }

            # Quartiles
            sorted_pairs = sorted(pairs, key=lambda x: x[0])
            q = len(sorted_pairs) // 4
            if q >= 5:
                lo = [h for _, h in sorted_pairs[:q]]
                hi = [h for _, h in sorted_pairs[-q:]]
                viewership_result["low_viewers_mean_hate"] = round(statistics.mean(lo), 4)
                viewership_result["high_viewers_mean_hate"] = round(statistics.mean(hi), 4)
                viewership_result["low_viewers_avg"] = round(
                    statistics.mean(v for v, _ in sorted_pairs[:q]))
                viewership_result["high_viewers_avg"] = round(
                    statistics.mean(v for v, _ in sorted_pairs[-q:]))

            print(f"    Pearson r={pr:.4f}, p={pp:.6f}")
            print(f"    Spearman ρ={sr:.4f}, p={spp:.6f}")
            print(f"    {'*** SIGNIFICANT ***' if viewership_result['significant'] else 'Not significant'}")
            if "low_viewers_mean_hate" in viewership_result:
                print(f"    Low viewers ({viewership_result['low_viewers_avg']:,.0f} avg): "
                      f"hate={viewership_result['low_viewers_mean_hate']:.4f}")
                print(f"    High viewers ({viewership_result['high_viewers_avg']:,.0f} avg): "
                      f"hate={viewership_result['high_viewers_mean_hate']:.4f}")
        elif len(pairs) < 20:
            print("    Too few matched windows for correlation")
    else:
        print("    No viewership data found")

    result = {
        "streamer": name,
        "score_column": score_col,
        "n_scored": len(scored),
        "global_mean_hate": round(statistics.mean(all_hate), 4),
        "global_median_hate": round(statistics.median(all_hate), 4),
        "global_pct_above_05": round(
            sum(1 for h in all_hate if h > 0.5) / len(all_hate) * 100, 2),
        "new_vs_established": new_vs_est,
        "per_user_comparison": per_user,
        "first_message": first_msg,
        "viewership_correlation": viewership_result,
    }

    sout = out_dir / name
    sout.mkdir(parents=True, exist_ok=True)
    out_path = sout / "roberta_analysis.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\n  → {out_path}")

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--roberta", "-r", required=True, help="roberta_results/ directory")
    parser.add_argument("--chat", "-c", required=True, help="chat_logs/ directory")
    parser.add_argument("--viewership", "-v", default=None, help="viewership_results/ directory")
    parser.add_argument("--output", "-o", default="roberta_analysis", help="Output directory")
    args = parser.parse_args()

    roberta_dir = Path(args.roberta)
    chat_dir = Path(args.chat)
    view_dir = Path(args.viewership) if args.viewership else None
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("  ROBERTA HATE SPEECH: NEW USERS + VIEWERSHIP")
    print("=" * 60)

    all_results = {}

    for sdir in sorted(roberta_dir.iterdir()):
        if not sdir.is_dir():
            continue
        name = sdir.name
        scored_path = sdir / "scored_messages.csv"
        chat_folder = chat_dir / name

        if not scored_path.exists():
            continue

        result = process_streamer(name, scored_path, chat_folder, view_dir, out)
        if result:
            all_results[name] = result

    # Cross-streamer summary
    if len(all_results) > 1:
        print(f"\n{'='*60}")
        print(f"  CROSS-STREAMER SUMMARY")
        print(f"{'='*60}")

        print(f"\n  NEW vs ESTABLISHED HATE SPEECH:")
        print(f"  {'Streamer':15s} {'New Mean':>9s} {'Est Mean':>9s} {'Δ':>8s} {'Sig':>5s}")
        print(f"  {'-'*50}")
        for name, r in sorted(all_results.items()):
            ne = r["new_vs_established"]
            sig = "YES" if ne.get("significant") else "no"
            print(f"  {name:15s} {ne.get('new_mean_hate','–'):>9} {ne.get('est_mean_hate','–'):>9} "
                  f"{ne.get('delta','–'):>+8} {sig:>5s}")

        print(f"\n  FIRST MESSAGE HATE (new users):")
        print(f"  {'Streamer':15s} {'1st Msg':>8s} {'Overall':>8s} {'Δ':>8s} {'Early→Late':>12s}")
        print(f"  {'-'*55}")
        for name, r in sorted(all_results.items()):
            fm = r["first_message"]
            el = f"{fm.get('early_mean','–')}→{fm.get('late_mean','–')}" if fm.get("early_mean") else "–"
            print(f"  {name:15s} {fm.get('first_msg_mean_hate','–'):>8} {fm.get('overall_mean_hate','–'):>8} "
                  f"{fm.get('delta','–'):>+8} {el:>12s}")

        print(f"\n  HATE SPEECH vs VIEWERSHIP:")
        print(f"  {'Streamer':15s} {'n':>6s} {'ρ':>7s} {'p':>10s} {'Sig':>5s} {'Lo-View':>9s} {'Hi-View':>9s}")
        print(f"  {'-'*58}")
        for name, r in sorted(all_results.items()):
            vc = r["viewership_correlation"]
            if not vc:
                print(f"  {name:15s} {'no viewership data':>45s}")
                continue
            sig = "YES" if vc.get("significant") else "no"
            print(f"  {name:15s} {vc.get('n_windows','–'):>6} {vc.get('spearman_r','–'):>7} "
                  f"{vc.get('spearman_p','–'):>10} {sig:>5s} "
                  f"{vc.get('low_viewers_mean_hate','–'):>9} {vc.get('high_viewers_mean_hate','–'):>9}")

    # Save combined
    combined_path = out / "roberta_combined.json"
    with open(combined_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\n  → {combined_path}")

    print(f"\n{'='*60}")
    print(f"  Done!")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
