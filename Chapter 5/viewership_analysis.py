#!/usr/bin/env python3
"""
Viewership × Toxicity Analysis (with Per-Attribute Correlations)
=================================================================
Merges 5-minute viewership snapshots with scored chat messages to answer:

  1. Does toxicity rise with audience size? (overall + per-attribute)
  2. Do viewers leave after toxic bursts?
  3. What % of viewers actually chat? (participation rate)
  4. Do follower gains correlate with toxicity?
  5. Raid detection — do viewer spikes bring toxicity?
  6. Stream warmup — how does toxicity change as a stream progresses?
  7. Per-attribute viewership correlations (INSULT, IDENTITY_ATTACK, THREAT)

Usage:
    python viewership_analysis.py \\
        --chat chat_logs/ \\
        --viewership stream_viewership/ \\
        --scored master_results/ \\
        --output viewership_results/

Install:
    pip install scipy
"""

import json
import csv
import sys
import re
import argparse
import statistics
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime, timedelta

try:
    from scipy import stats as sp
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

EMOTE_RE = re.compile(r'\[emote:\d+:[^\]]+\]')
ATTRS = ["TOXICITY", "INSULT", "PROFANITY", "IDENTITY_ATTACK", "THREAT", "SEVERE_TOXICITY"]


# ═══════════════════════════════════════════════════════════════
#  LOADING
# ═══════════════════════════════════════════════════════════════

def parse_ts(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def load_viewership_csv(path):
    records = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            dt_str = (row.get("Date Time") or "").strip()
            viewers = (row.get("Viewers") or "0").strip().replace(",", "")
            fgain = (row.get("Followers gain") or "N/A").strip().replace(",", "")
            for fmt in ["%b %d, %Y %H:%M", "%Y-%m-%d %H:%M"]:
                try:
                    dt = datetime.strptime(dt_str, fmt)
                    break
                except ValueError:
                    continue
            else:
                continue
            try:
                v = int(viewers)
            except ValueError:
                v = 0
            try:
                fg = int(fgain)
            except ValueError:
                fg = None
            records.append({"datetime": dt, "viewers": v, "followers_gain": fg})
    records.sort(key=lambda r: r["datetime"])
    return records


def load_chat_messages(folder):
    msgs = []
    for f in sorted(folder.glob("*.json")):
        with open(f, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            raw = data if isinstance(data, list) else data.get("messages", data.get("data", []))
            msgs.extend(raw)
    msgs = [m for m in msgs if isinstance(m, dict) and m.get("createdAt")]
    msgs.sort(key=lambda m: m["createdAt"])
    return msgs


def load_scored_messages(scored_dir, streamer_name):
    candidates = [
        scored_dir / streamer_name / "scored_messages.csv",
        scored_dir / f"{streamer_name}_scored_messages.csv",
    ]
    for p in candidates:
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                return list(csv.DictReader(f))
    return None


def discover_streamers(chat_dir, view_dir):
    chat_subs = {d.name: d for d in chat_dir.iterdir() if d.is_dir()}
    view_subs = {d.name: d for d in view_dir.iterdir() if d.is_dir()}
    common = set(chat_subs.keys()) & set(view_subs.keys())
    if not common:
        return {}
    return {name: (chat_subs[name], view_subs[name]) for name in sorted(common)}


# ═══════════════════════════════════════════════════════════════
#  STREAM SEGMENTATION + WINDOWING
# ═══════════════════════════════════════════════════════════════

def segment_into_streams(viewership_records, gap_seconds=3600):
    if not viewership_records:
        return []
    streams = []
    current = [viewership_records[0]]
    for rec in viewership_records[1:]:
        gap = (rec["datetime"] - current[-1]["datetime"]).total_seconds()
        if gap > gap_seconds:
            streams.append(current)
            current = [rec]
        else:
            current.append(rec)
    if current:
        streams.append(current)
    return streams


def match_chat_to_viewership(chat_msgs, view_stream, scored_msgs=None):
    if not view_stream:
        return []

    scored_lookup = {}
    if scored_msgs:
        for s in scored_msgs:
            ts = s.get("createdAt", "")
            if ts:
                scored_lookup[ts] = s

    windows = []
    for i, vrec in enumerate(view_stream):
        wstart = vrec["datetime"]
        wend = view_stream[i + 1]["datetime"] if i + 1 < len(view_stream) else wstart + timedelta(minutes=5)

        w_msgs = []
        w_tox = []
        w_users = set()
        w_emote_only = 0
        w_text_only = 0

        for m in chat_msgs:
            try:
                mdt = parse_ts(m["createdAt"]).replace(tzinfo=None)
            except:
                continue
            if wstart <= mdt < wend:
                w_msgs.append(m)
                w_users.add(str(m.get("userId", "")))
                content = m.get("content", "")
                stripped = EMOTE_RE.sub("", content).strip()
                if not stripped and EMOTE_RE.search(content):
                    w_emote_only += 1
                elif stripped:
                    w_text_only += 1
                scored = scored_lookup.get(m["createdAt"])
                if scored:
                    try:
                        w_tox.append(float(scored.get("TOXICITY", 0)))
                    except:
                        pass

        window = {
            "datetime": wstart.isoformat(),
            "viewers": vrec["viewers"],
            "followers_gain": vrec["followers_gain"],
            "n_messages": len(w_msgs),
            "n_unique_chatters": len(w_users),
            "n_text": w_text_only,
            "n_emote": w_emote_only,
            "participation_rate": round(len(w_users) / max(vrec["viewers"], 1) * 100, 3),
            "msgs_per_viewer": round(len(w_msgs) / max(vrec["viewers"], 1), 4),
        }

        if w_tox:
            window["mean_toxicity"] = round(statistics.mean(w_tox), 4)
            window["max_toxicity"] = round(max(w_tox), 4)
            window["pct_toxic_05"] = round(sum(1 for t in w_tox if t > 0.5) / len(w_tox) * 100, 1)
            window["n_scored"] = len(w_tox)
        else:
            window["mean_toxicity"] = None
            window["max_toxicity"] = None
            window["pct_toxic_05"] = None
            window["n_scored"] = 0

        window["minutes_in"] = round((wstart - view_stream[0]["datetime"]).total_seconds() / 60, 1)
        windows.append(window)

    return windows


# ═══════════════════════════════════════════════════════════════
#  ANALYSIS FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def analyze_toxicity_vs_viewers(windows):
    pairs = [(w["viewers"], w["mean_toxicity"])
             for w in windows if w["mean_toxicity"] is not None and w["viewers"] > 0]
    if len(pairs) < 10:
        return {"note": "Too few windows with toxicity data"}
    viewers, toxes = zip(*pairs)
    result = {"n_windows": len(pairs)}
    if HAS_SCIPY:
        pr, pp = sp.pearsonr(viewers, toxes)
        sr, spp = sp.spearmanr(viewers, toxes)
        result.update({"pearson_r": round(pr, 4), "pearson_p": round(pp, 6),
                        "spearman_r": round(sr, 4), "spearman_p": round(spp, 6),
                        "significant_p05": pp < 0.05 or spp < 0.05})
    sorted_pairs = sorted(pairs, key=lambda x: x[0])
    q = len(sorted_pairs) // 4
    if q >= 3:
        result["viewer_quartile_comparison"] = {
            "lowest_25pct_viewers": {
                "mean_viewers": round(statistics.mean(v for v, _ in sorted_pairs[:q])),
                "mean_toxicity": round(statistics.mean(t for _, t in sorted_pairs[:q]), 4),
            },
            "highest_25pct_viewers": {
                "mean_viewers": round(statistics.mean(v for v, _ in sorted_pairs[-q:])),
                "mean_toxicity": round(statistics.mean(t for _, t in sorted_pairs[-q:]), 4),
            },
        }
    return result


def analyze_viewer_departure(windows, burst_threshold=0.35):
    results = {"burst_threshold": burst_threshold}
    after_toxic = []
    after_clean = []
    for i in range(len(windows) - 1):
        w = windows[i]
        nxt = windows[i + 1]
        if w["viewers"] == 0:
            continue
        change_pct = (nxt["viewers"] - w["viewers"]) / w["viewers"] * 100
        if w["mean_toxicity"] is not None and w["mean_toxicity"] >= burst_threshold:
            after_toxic.append(change_pct)
        elif w["mean_toxicity"] is not None and w["mean_toxicity"] < 0.1:
            after_clean.append(change_pct)
    if after_toxic and after_clean:
        results.update({
            "n_toxic_windows": len(after_toxic),
            "n_clean_windows": len(after_clean),
            "mean_viewer_change_after_toxic": round(statistics.mean(after_toxic), 2),
            "mean_viewer_change_after_clean": round(statistics.mean(after_clean), 2),
            "median_viewer_change_after_toxic": round(statistics.median(after_toxic), 2),
            "median_viewer_change_after_clean": round(statistics.median(after_clean), 2),
        })
        if HAS_SCIPY and len(after_toxic) >= 5 and len(after_clean) >= 5:
            stat, pval = sp.mannwhitneyu(after_toxic, after_clean, alternative='less')
            results["mann_whitney_p"] = round(pval, 6)
            results["significant_viewer_loss"] = pval < 0.05
    return results


def analyze_participation_rate(windows):
    rates = [w["participation_rate"] for w in windows if w["viewers"] > 100]
    if not rates:
        return {}
    return {
        "mean_participation_pct": round(statistics.mean(rates), 3),
        "median_participation_pct": round(statistics.median(rates), 3),
        "min_participation_pct": round(min(rates), 3),
        "max_participation_pct": round(max(rates), 3),
        "n_windows": len(rates),
    }


def analyze_followers_vs_toxicity(windows):
    pairs = [(w["followers_gain"], w["mean_toxicity"])
             for w in windows
             if w["followers_gain"] is not None and w["mean_toxicity"] is not None]
    if len(pairs) < 10:
        return {"note": "Too few windows"}
    fgains, toxes = zip(*pairs)
    result = {"n_windows": len(pairs)}
    if HAS_SCIPY:
        sr, spp = sp.spearmanr(fgains, toxes)
        result.update({"spearman_r": round(sr, 4), "spearman_p": round(spp, 6),
                        "significant_p05": spp < 0.05})
    return result


def detect_raids(windows, spike_threshold=1.5):
    raids = []
    for i in range(1, len(windows)):
        prev = windows[i - 1]["viewers"]
        curr = windows[i]["viewers"]
        if prev > 100 and curr > prev * spike_threshold:
            raids.append({
                "datetime": windows[i]["datetime"],
                "viewers_before": prev, "viewers_after": curr,
                "increase_pct": round((curr - prev) / prev * 100, 1),
                "toxicity_before": windows[i - 1].get("mean_toxicity"),
                "toxicity_after": windows[i].get("mean_toxicity"),
                "toxicity_next_3": round(statistics.mean(
                    w["mean_toxicity"] for w in windows[i:i + 3]
                    if w.get("mean_toxicity") is not None
                ), 4) if any(w.get("mean_toxicity") for w in windows[i:i + 3]) else None,
            })
    return raids


def analyze_stream_warmup(windows):
    if not windows:
        return {}
    total_mins = windows[-1]["minutes_in"]
    if total_mins < 20:
        return {"note": "Stream too short"}
    q_len = total_mins / 4
    quarters = defaultdict(list)
    for w in windows:
        if w["mean_toxicity"] is None:
            continue
        q = min(3, int(w["minutes_in"] / q_len))
        quarters[q].append(w)
    result = {}
    labels = ["first_quarter", "second_quarter", "third_quarter", "fourth_quarter"]
    for i in range(4):
        ws = quarters.get(i, [])
        if ws:
            result[labels[i]] = {
                "n_windows": len(ws),
                "mean_toxicity": round(statistics.mean(w["mean_toxicity"] for w in ws), 4),
                "mean_viewers": round(statistics.mean(w["viewers"] for w in ws)),
                "mean_msgs_per_window": round(statistics.mean(w["n_messages"] for w in ws), 1),
                "mean_participation_pct": round(statistics.mean(w["participation_rate"] for w in ws), 3),
            }
    return result


# ═══════════════════════════════════════════════════════════════
#  PER-ATTRIBUTE VIEWERSHIP CORRELATIONS
# ═══════════════════════════════════════════════════════════════

def analyze_attribute_viewership(scored_path, window_datetimes, viewers_list):
    """
    Fast binning: round scored message timestamps to 5-min epoch keys,
    join with viewership windows, compute per-attribute correlations.
    """
    # Build window key lookup
    win_keys = {}
    for i, dt_str in enumerate(window_datetimes):
        for fmt in [None, "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"]:
            try:
                if fmt is None:
                    dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00")).replace(tzinfo=None)
                else:
                    dt = datetime.strptime(dt_str, fmt)
                epoch = int(dt.timestamp())
                win_keys[epoch - (epoch % 300)] = i
                break
            except:
                continue

    n_windows = len(window_datetimes)
    window_attrs = [defaultdict(list) for _ in range(n_windows)]
    matched = 0

    with open(scored_path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ts = row.get("createdAt", "")
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
            except:
                continue
            epoch = int(dt.timestamp())
            key = epoch - (epoch % 300)
            idx = win_keys.get(key) or win_keys.get(key - 300) or win_keys.get(key + 300)
            if idx is not None:
                for attr in ATTRS:
                    val = row.get(attr)
                    if val:
                        try:
                            window_attrs[idx][attr].append(float(val))
                        except:
                            pass
                matched += 1

    print(f"    Attribute viewership: {matched:,} messages matched to windows")

    # Compute per-attribute correlations
    results = {}
    for attr in ATTRS:
        pairs = [(viewers_list[i], statistics.mean(wa[attr]))
                 for i, wa in enumerate(window_attrs)
                 if attr in wa and wa[attr] and viewers_list[i] > 100]

        if len(pairs) < 20:
            results[attr] = {"n": len(pairs), "note": "Too few"}
            continue

        vs, ts = zip(*pairs)
        r = {"n": len(pairs)}
        if HAS_SCIPY:
            pr, pp = sp.pearsonr(vs, ts)
            sr, spp = sp.spearmanr(vs, ts)
            r.update({"pearson_r": round(pr, 4), "pearson_p": round(pp, 6),
                       "spearman_r": round(sr, 4), "spearman_p": round(spp, 6),
                       "significant": spp < 0.05})

        sorted_pairs = sorted(pairs, key=lambda x: x[0])
        q = len(sorted_pairs) // 4
        if q >= 5:
            r["low_viewers_mean"] = round(statistics.mean(t for _, t in sorted_pairs[:q]), 4)
            r["high_viewers_mean"] = round(statistics.mean(t for _, t in sorted_pairs[-q:]), 4)

        results[attr] = r

    return results


# ═══════════════════════════════════════════════════════════════
#  MAIN PIPELINE
# ═══════════════════════════════════════════════════════════════

def process_streamer(name, chat_folder, view_folder, scored_dir, out_dir):
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")

    sdir = out_dir / name
    sdir.mkdir(parents=True, exist_ok=True)

    print("  Loading chat messages...")
    chat_msgs = load_chat_messages(chat_folder)
    print(f"    {len(chat_msgs):,} messages")

    scored_msgs = None
    scored_path = None
    if scored_dir:
        scored_msgs = load_scored_messages(scored_dir, name)
        scored_path = scored_dir / name / "scored_messages.csv"
        if scored_msgs:
            print(f"    {len(scored_msgs):,} scored messages loaded")

    print("  Loading viewership data...")
    all_view_records = []
    for vf in sorted(view_folder.glob("*.csv")):
        recs = load_viewership_csv(vf)
        all_view_records.extend(recs)
        print(f"    {vf.name}: {len(recs)} records")

    all_view_records.sort(key=lambda r: r["datetime"])
    if not all_view_records:
        print("  [SKIP] No viewership data")
        return None

    streams = segment_into_streams(all_view_records)
    print(f"  Found {len(streams)} individual streams")

    all_windows = []
    stream_summaries = []

    for si, view_stream in enumerate(streams):
        stream_start = view_stream[0]["datetime"]
        stream_end = view_stream[-1]["datetime"]
        dur_hrs = (stream_end - stream_start).total_seconds() / 3600

        windows = match_chat_to_viewership(chat_msgs, view_stream, scored_msgs)
        all_windows.extend(windows)

        peak_viewers = max(w["viewers"] for w in windows) if windows else 0
        mean_viewers = round(statistics.mean(w["viewers"] for w in windows)) if windows else 0
        total_msgs = sum(w["n_messages"] for w in windows)
        tox_windows = [w for w in windows if w["mean_toxicity"] is not None]

        summary = {
            "stream_index": si + 1,
            "date": stream_start.strftime("%Y-%m-%d"),
            "start": stream_start.strftime("%H:%M"),
            "duration_hours": round(dur_hrs, 2),
            "peak_viewers": peak_viewers,
            "mean_viewers": mean_viewers,
            "total_messages": total_msgs,
            "n_windows": len(windows),
        }
        if tox_windows:
            summary["mean_toxicity"] = round(statistics.mean(w["mean_toxicity"] for w in tox_windows), 4)
        stream_summaries.append(summary)
        print(f"    Stream {si+1}: {stream_start.strftime('%Y-%m-%d %H:%M')} "
              f"({dur_hrs:.1f}h, peak {peak_viewers:,}, {total_msgs:,} msgs)")

    print("\n  Running analyses...")
    results = {
        "streamer": name,
        "total_streams": len(streams),
        "total_viewership_records": len(all_view_records),
        "total_chat_messages": len(chat_msgs),
        "total_windows": len(all_windows),
        "stream_summaries": stream_summaries,
    }

    results["toxicity_vs_viewers"] = analyze_toxicity_vs_viewers(all_windows)
    r = results["toxicity_vs_viewers"]
    if "spearman_r" in r:
        print(f"    Tox vs viewers: ρ={r['spearman_r']}, p={r['spearman_p']}")

    results["viewer_departure"] = analyze_viewer_departure(all_windows)
    vd = results["viewer_departure"]
    if "mean_viewer_change_after_toxic" in vd:
        print(f"    After toxic: {vd['mean_viewer_change_after_toxic']:+.2f}% | "
              f"After clean: {vd['mean_viewer_change_after_clean']:+.2f}%")

    results["participation_rate"] = analyze_participation_rate(all_windows)
    pr = results["participation_rate"]
    if "mean_participation_pct" in pr:
        print(f"    Participation: {pr['mean_participation_pct']:.2f}% of viewers chat")

    results["followers_vs_toxicity"] = analyze_followers_vs_toxicity(all_windows)
    results["detected_raids"] = detect_raids(all_windows)[:10]

    # Warmup averaged across streams
    all_warmups = []
    for view_stream in streams:
        windows = match_chat_to_viewership(chat_msgs, view_stream, scored_msgs)
        wu = analyze_stream_warmup(windows)
        if wu and "first_quarter" in wu:
            all_warmups.append(wu)
    if all_warmups:
        avg_warmup = {}
        for q in ["first_quarter", "second_quarter", "third_quarter", "fourth_quarter"]:
            q_data = [w[q] for w in all_warmups if q in w]
            if q_data:
                avg_warmup[q] = {
                    "mean_toxicity": round(statistics.mean(d["mean_toxicity"] for d in q_data), 4),
                    "mean_viewers": round(statistics.mean(d["mean_viewers"] for d in q_data)),
                    "mean_participation_pct": round(statistics.mean(d["mean_participation_pct"] for d in q_data), 3),
                    "n_streams": len(q_data),
                }
        results["stream_warmup_averaged"] = avg_warmup

    # ── Per-attribute viewership correlations ──
    if scored_path and scored_path.exists() and all_windows:
        datetimes = [w["datetime"] for w in all_windows]
        viewers_list = [w["viewers"] for w in all_windows]
        attr_results = analyze_attribute_viewership(scored_path, datetimes, viewers_list)
        results["attribute_viewership"] = attr_results

        print(f"    Per-attribute viewership:")
        for attr in ["TOXICITY", "INSULT", "IDENTITY_ATTACK", "THREAT"]:
            ar = attr_results.get(attr, {})
            rho = ar.get("spearman_r", "–")
            sig = "YES" if ar.get("significant") else "no"
            print(f"      {attr:20s} ρ={rho:>7}  sig={sig}")

    # Export windowed CSV
    if all_windows:
        csv_path = sdir / "windowed_data.csv"
        keys = list(all_windows[0].keys())
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            for row in all_windows:
                w.writerow(row)

    json_path = sdir / "viewership_analysis.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"  → {json_path}")

    return results


def cross_streamer_summary(all_results, out_dir):
    print(f"\n{'='*60}")
    print(f"  CROSS-STREAMER VIEWERSHIP SUMMARY")
    print(f"{'='*60}")

    # Main table
    print(f"\n  {'Streamer':15s} {'ρ(tox,view)':>12s} {'Particip%':>10s} "
          f"{'AfterToxic':>11s} {'AfterClean':>11s} {'Raids':>6s}")
    print("  " + "-" * 70)
    for name, r in sorted(all_results.items()):
        if not r:
            continue
        tv = r.get("toxicity_vs_viewers", {})
        pr = r.get("participation_rate", {})
        vd = r.get("viewer_departure", {})
        rho = f"{tv['spearman_r']:.3f}" if isinstance(tv.get('spearman_r'), float) else "–"
        part = f"{pr['mean_participation_pct']:.2f}%" if isinstance(pr.get('mean_participation_pct'), float) else "–"
        at = f"{vd['mean_viewer_change_after_toxic']:+.1f}%" if isinstance(vd.get('mean_viewer_change_after_toxic'), (int, float)) else "–"
        ac = f"{vd['mean_viewer_change_after_clean']:+.1f}%" if isinstance(vd.get('mean_viewer_change_after_clean'), (int, float)) else "–"
        print(f"  {name:15s} {rho:>12s} {part:>10s} {at:>11s} {ac:>11s} {len(r.get('detected_raids',[])):>6d}")

    # Attribute viewership table
    print(f"\n  PER-ATTRIBUTE × VIEWERSHIP (Spearman ρ):")
    focus = ["TOXICITY", "INSULT", "IDENTITY_ATTACK", "THREAT"]
    print(f"  {'Streamer':15s}", end="")
    for a in focus:
        print(f" {a:>16s}", end="")
    print()
    print(f"  {'-'*80}")
    for name, r in sorted(all_results.items()):
        if not r:
            continue
        av = r.get("attribute_viewership", {})
        print(f"  {name:15s}", end="")
        for a in focus:
            ar = av.get(a, {})
            rho = ar.get("spearman_r")
            sig = ar.get("significant", False)
            if rho is not None:
                print(f" {rho:>+14.4f}{'*' if sig else ' '}", end="")
            else:
                print(f" {'–':>15s}", end="")
        print()

    with open(out_dir / "cross_streamer_viewership.json", "w", encoding="utf-8") as f:
        json.dump({n: r for n, r in all_results.items() if r}, f, indent=2, default=str)


def main():
    parser = argparse.ArgumentParser(description="Viewership × Toxicity analysis")
    parser.add_argument("--chat", "-c", required=True)
    parser.add_argument("--viewership", "-v", required=True)
    parser.add_argument("--scored", "-s", default=None)
    parser.add_argument("--output", "-o", default="viewership_results")
    args = parser.parse_args()

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    chat_dir = Path(args.chat)
    view_dir = Path(args.viewership)
    scored_dir = Path(args.scored) if args.scored else None

    streamers = discover_streamers(chat_dir, view_dir)
    if not streamers:
        print("No matching streamer folders found")
        sys.exit(1)

    print(f"Matched {len(streamers)} streamer(s): {', '.join(streamers.keys())}")

    all_results = {}
    for name, (chat_folder, view_folder) in streamers.items():
        result = process_streamer(name, chat_folder, view_folder, scored_dir, out)
        all_results[name] = result

    if len(all_results) > 1:
        cross_streamer_summary(all_results, out)

    print(f"\nDone! Results in {out}/")


if __name__ == "__main__":
    main()