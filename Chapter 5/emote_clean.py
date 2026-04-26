#!/usr/bin/env python3
"""
Clean Emote, Spam & Temporal Analysis
========================================
Combined analysis:

  1. SPAM DETECTION — deduplicate repeated messages
  2. CONTAGION RECOMPUTE — with and without spam
  3. MIXED vs TEXT-ONLY — are emote-containing messages more toxic?
  4. TOP EMOTES → TOXICITY — popularity-first, test both direct + context
  5. TEMPORAL PATTERNS — toxicity by hour and day of week (deduped)

Usage:
    python emote_clean.py --scored master_results/ --chat chat_logs/
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

try:
    from scipy import stats as sp
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

EMOTE_RE = re.compile(r'\[emote:\d+:([^\]]+)\]')
EMOTE_TAG_RE = re.compile(r'\[emote:\d+:[^\]]+\]')
ATTRS = ["TOXICITY", "SEVERE_TOXICITY", "INSULT", "PROFANITY", "IDENTITY_ATTACK", "THREAT"]


def load_scored(path):
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


def categorize(content):
    stripped = EMOTE_TAG_RE.sub("", content).strip()
    has_emotes = bool(EMOTE_TAG_RE.search(content))
    if has_emotes and not stripped:
        return "emote_only"
    elif has_emotes:
        return "mixed"
    return "text_only"


# ═══════════════════════════════════════════════════════════════
#  1. SPAM DETECTION
# ═══════════════════════════════════════════════════════════════

def detect_spam(scored, window=10):
    sorted_msgs = sorted(scored, key=lambda m: m.get("createdAt", ""))
    spam_count = 0
    deduped = []
    recent_texts = []

    for i, msg in enumerate(sorted_msgs):
        text = msg.get("clean_text", msg.get("content", "")).strip().lower()
        uid = msg.get("userId", "")
        is_spam = False

        if i > 0:
            prev = sorted_msgs[i - 1]
            prev_text = prev.get("clean_text", prev.get("content", "")).strip().lower()
            if prev.get("userId") == uid and prev_text == text and text:
                is_spam = True

        if not is_spam and text and len(text) > 2:
            if sum(1 for t in recent_texts[-window:] if t == text) >= 2:
                is_spam = True

        recent_texts.append(text)
        if len(recent_texts) > window:
            recent_texts.pop(0)

        if is_spam:
            spam_count += 1
        else:
            deduped.append(msg)

    return {
        "total": len(sorted_msgs),
        "spam": spam_count,
        "spam_pct": round(spam_count / max(len(sorted_msgs), 1) * 100, 2),
        "deduped": deduped,
    }


# ═══════════════════════════════════════════════════════════════
#  2. CONTAGION
# ═══════════════════════════════════════════════════════════════

def contagion_test(scored, window=5, threshold=0.5, label=""):
    sorted_msgs = sorted(scored, key=lambda m: m.get("createdAt", ""))
    tox = []
    for m in sorted_msgs:
        try:
            tox.append(float(m["TOXICITY"]))
        except:
            continue
    if len(tox) < window * 2:
        return {}
    after_toxic = []
    after_clean = []
    for i in range(len(tox) - window):
        following = statistics.mean(tox[i + 1:i + 1 + window])
        if tox[i] >= threshold:
            after_toxic.append(following)
        elif tox[i] < 0.1:
            after_clean.append(following)
    result = {"label": label, "n_toxic": len(after_toxic), "n_clean": len(after_clean)}
    if after_toxic and after_clean:
        result["mean_after_toxic"] = round(statistics.mean(after_toxic), 4)
        result["mean_after_clean"] = round(statistics.mean(after_clean), 4)
        result["ratio"] = round(statistics.mean(after_toxic) / max(statistics.mean(after_clean), 0.0001), 2)
        if HAS_SCIPY and len(after_toxic) >= 5 and len(after_clean) >= 5:
            stat, pval = sp.mannwhitneyu(after_toxic, after_clean, alternative='greater')
            result["p"] = round(pval, 6)
            result["significant"] = pval < 0.05
    return result


# ═══════════════════════════════════════════════════════════════
#  3. DEDUPED ATTRIBUTE STATS + TEMPORAL
# ═══════════════════════════════════════════════════════════════

def compute_deduped_stats(deduped):
    if not deduped:
        return {}, {}

    n = len(deduped)
    attr_stats = {}
    for attr in ATTRS:
        vals = []
        for r in deduped:
            try:
                vals.append(float(r[attr]))
            except:
                pass
        if vals:
            attr_stats[attr] = {
                "mean": round(statistics.mean(vals), 4),
                "median": round(statistics.median(vals), 4),
                "pct_above_05": round(sum(1 for v in vals if v > 0.5) / len(vals) * 100, 2),
                "pct_above_07": round(sum(1 for v in vals if v > 0.7) / len(vals) * 100, 2),
            }

    # Temporal
    hourly = defaultdict(list)
    daily = defaultdict(list)
    for r in deduped:
        ts = r.get("createdAt", "")
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            hourly[dt.hour].append(float(r["TOXICITY"]))
            daily[dt.strftime("%A")].append(float(r["TOXICITY"]))
        except:
            pass

    temporal = {}
    if hourly:
        temporal["by_hour"] = {h: {"mean": round(statistics.mean(v), 4), "n": len(v)}
                               for h, v in sorted(hourly.items())}
        temporal["peak_hour"] = max(temporal["by_hour"], key=lambda h: temporal["by_hour"][h]["mean"])
        temporal["lowest_hour"] = min(temporal["by_hour"], key=lambda h: temporal["by_hour"][h]["mean"])
    if daily:
        temporal["by_day"] = {d: {"mean": round(statistics.mean(v), 4), "n": len(v)}
                              for d, v in daily.items()}
        temporal["peak_day"] = max(temporal["by_day"], key=lambda d: temporal["by_day"][d]["mean"])
        temporal["lowest_day"] = min(temporal["by_day"], key=lambda d: temporal["by_day"][d]["mean"])

    return attr_stats, temporal


# ═══════════════════════════════════════════════════════════════
#  4–5. EMOTE ANALYSIS
# ═══════════════════════════════════════════════════════════════

def process_streamer(name, chat_folder, scored_path):
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")

    scored = load_scored(scored_path)
    chat_msgs = load_chat(chat_folder)
    print(f"  {len(scored):,} scored | {len(chat_msgs):,} total chat")

    # ── SPAM ──
    print(f"\n  [1] SPAM DETECTION")
    spam = detect_spam(scored)
    deduped = spam["deduped"]
    print(f"    Spam: {spam['spam']:,} ({spam['spam_pct']}%) | Deduped: {len(deduped):,}")

    # ── CONTAGION ──
    print(f"\n  [2] CONTAGION (original vs deduped)")
    cg_orig = contagion_test(scored, label="original")
    cg_dedup = contagion_test(deduped, label="deduped")
    print(f"    Original: ratio={cg_orig.get('ratio','?')} sig={cg_orig.get('significant','?')}")
    print(f"    Deduped:  ratio={cg_dedup.get('ratio','?')} sig={cg_dedup.get('significant','?')}")

    # ── DEDUPED STATS + TEMPORAL ──
    print(f"\n  [3] DEDUPED STATS + TEMPORAL")
    attr_stats, temporal = compute_deduped_stats(deduped)
    for attr in ["TOXICITY", "INSULT", "IDENTITY_ATTACK", "THREAT"]:
        a = attr_stats.get(attr, {})
        print(f"    {attr:20s} mean={a.get('mean','–'):>7} >0.5={a.get('pct_above_05','–')}%")
    if temporal.get("peak_hour") is not None:
        print(f"    Peak hour: {temporal['peak_hour']}:00 | Lowest: {temporal['lowest_hour']}:00")
    if temporal.get("peak_day"):
        print(f"    Peak day: {temporal['peak_day']} | Lowest: {temporal['lowest_day']}")

    # ── MIXED vs TEXT-ONLY ──
    print(f"\n  [4] MIXED vs TEXT-ONLY MESSAGES")
    text_only_tox = []
    mixed_tox = []
    for s in scored:
        content = s.get("content", s.get("clean_text", ""))
        cat = categorize(content)
        try:
            tox = float(s["TOXICITY"])
        except:
            continue
        if cat == "text_only":
            text_only_tox.append(tox)
        elif cat == "mixed":
            mixed_tox.append(tox)

    mixed_vs_text = {"n_text": len(text_only_tox), "n_mixed": len(mixed_tox)}
    if text_only_tox and mixed_tox:
        tm, mm = statistics.mean(text_only_tox), statistics.mean(mixed_tox)
        mixed_vs_text.update({
            "text_mean": round(tm, 4), "mixed_mean": round(mm, 4),
            "delta": round(mm - tm, 4),
            "mixed_more_toxic_pct": round((mm - tm) / max(tm, 0.001) * 100, 1),
            "text_pct_above_05": round(sum(1 for t in text_only_tox if t > 0.5) / len(text_only_tox) * 100, 2),
            "mixed_pct_above_05": round(sum(1 for t in mixed_tox if t > 0.5) / len(mixed_tox) * 100, 2),
        })
        if HAS_SCIPY:
            stat, pval = sp.mannwhitneyu(mixed_tox, text_only_tox, alternative='greater')
            mixed_vs_text["p"] = round(pval, 8)
            mixed_vs_text["significant"] = pval < 0.05
        print(f"    Text: mean={tm:.4f} >0.5={mixed_vs_text['text_pct_above_05']:.1f}%")
        print(f"    Mixed: mean={mm:.4f} >0.5={mixed_vs_text['mixed_pct_above_05']:.1f}% "
              f"(Δ={mixed_vs_text['delta']:+.4f}, {mixed_vs_text['mixed_more_toxic_pct']:+.1f}%)")
        if "p" in mixed_vs_text:
            print(f"    p={mixed_vs_text['p']:.8f} {'*** SIG ***' if mixed_vs_text['significant'] else 'ns'}")

    # ── TOP EMOTES ──
    print(f"\n  [5] TOP EMOTES BY POPULARITY → TOXICITY")
    emote_users = defaultdict(set)
    emote_total = Counter()
    for msg in chat_msgs:
        uid = str(msg.get("userId", ""))
        for e in EMOTE_RE.findall(msg.get("content", "")):
            emote_users[e].add(uid)
            emote_total[e] += 1

    emote_popularity = sorted(emote_users.items(), key=lambda x: len(x[1]), reverse=True)
    total_chatters = len(set(str(m.get("userId", "")) for m in chat_msgs))
    top_n = 30
    top_emotes = emote_popularity[:top_n]
    top_names = set(e for e, _ in top_emotes)

    print(f"    {len(emote_popularity):,} emotes, {total_chatters:,} chatters")
    print(f"\n    Top {top_n} by unique users:")
    print(f"    {'#':>3s} {'Emote':25s} {'Users':>7s} {'Uses':>8s}")
    print(f"    {'-'*48}")
    for rank, (emote, users) in enumerate(top_emotes, 1):
        print(f"    {rank:3d} {emote:25s} {len(users):7,d} {emote_total[emote]:8,d}")

    # Scored lookup
    scored_lookup = {}
    for s in scored:
        key = (s.get("userId", ""), s.get("createdAt", ""))
        try:
            scored_lookup[key] = float(s["TOXICITY"])
        except:
            pass

    # ── DIRECT: emote in scored mixed message ──
    emote_direct = defaultdict(list)
    all_scored_tox = []
    for s in scored:
        content = s.get("content", s.get("clean_text", ""))
        try:
            tox = float(s["TOXICITY"])
        except:
            continue
        all_scored_tox.append(tox)
        for e in EMOTE_RE.findall(content):
            if e in top_names:
                emote_direct[e].append(tox)

    overall_mean = statistics.mean(all_scored_tox) if all_scored_tox else 0

    direct_results = []
    print(f"\n    DIRECT (emote in scored msg, vs overall {overall_mean:.4f}):")
    print(f"    {'#':>3s} {'Emote':25s} {'n':>7s} {'Mean':>7s} {'Δ':>8s} {'>0.5%':>6s} {'Sig':>5s}")
    print(f"    {'-'*65}")
    for rank, (emote, users) in enumerate(top_emotes, 1):
        scores = emote_direct.get(emote, [])
        entry = {"rank": rank, "emote": emote, "n_users": len(users), "n_direct": len(scores)}
        if len(scores) >= 10:
            m = statistics.mean(scores)
            entry.update({"mean_tox": round(m, 4), "delta": round(m - overall_mean, 4),
                          "pct_above_05": round(sum(1 for s in scores if s > 0.5) / len(scores) * 100, 1)})
            sig_str = "–"
            if HAS_SCIPY and len(scores) >= 20 and text_only_tox:
                stat, pval = sp.mannwhitneyu(scores, text_only_tox, alternative='two-sided')
                entry["p"] = round(pval, 6)
                entry["significant"] = pval < 0.05
                sig_str = "YES" if pval < 0.05 else "no"
            print(f"    {rank:3d} {emote:25s} {len(scores):7,d} {m:7.4f} {m-overall_mean:>+7.4f} "
                  f"{entry['pct_above_05']:5.1f}% {sig_str:>5s}")
        else:
            print(f"    {rank:3d} {emote:25s} {len(scores):7,d} {'(few)':>30s}")
        direct_results.append(entry)

    # ── CONTEXT: 30-second windows ──
    window_data = defaultdict(lambda: {"emotes": set(), "tox_scores": []})
    for msg in chat_msgs:
        ts = msg.get("createdAt", "")
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except:
            continue
        epoch = int(dt.timestamp())
        win_key = epoch - (epoch % 30)
        for e in EMOTE_RE.findall(msg.get("content", "")):
            window_data[win_key]["emotes"].add(e)
        key = (str(msg.get("userId", "")), ts)
        if key in scored_lookup:
            window_data[win_key]["tox_scores"].append(scored_lookup[key])

    context_results = []
    print(f"\n    CONTEXT (30s windows):")
    print(f"    {'#':>3s} {'Emote':25s} {'Win+':>6s} {'Win-':>6s} {'Here':>7s} {'Base':>7s} {'Δ':>8s} {'Sig':>5s}")
    print(f"    {'-'*72}")

    for rank, (emote, users) in enumerate(top_emotes, 1):
        present = []
        absent = []
        for wk, wd in window_data.items():
            if not wd["tox_scores"]:
                continue
            mt = statistics.mean(wd["tox_scores"])
            if emote in wd["emotes"]:
                present.append(mt)
            else:
                absent.append(mt)

        entry = {"rank": rank, "emote": emote, "n_users": len(users),
                 "n_win_present": len(present), "n_win_absent": len(absent)}

        if len(present) >= 20 and len(absent) >= 20:
            mp, ma = statistics.mean(present), statistics.mean(absent)
            delta = mp - ma
            entry.update({"mean_present": round(mp, 4), "mean_absent": round(ma, 4),
                          "delta": round(delta, 4)})
            sig_str = "–"
            if HAS_SCIPY:
                stat, pval = sp.mannwhitneyu(present, absent, alternative='two-sided')
                entry["p"] = round(pval, 6)
                entry["significant"] = pval < 0.05
                sig_str = "YES" if pval < 0.05 else "no"
            print(f"    {rank:3d} {emote:25s} {len(present):6,d} {len(absent):6,d} "
                  f"{mp:7.4f} {ma:7.4f} {delta:>+7.4f} {sig_str:>5s}")
        else:
            print(f"    {rank:3d} {emote:25s} {len(present):6,d} {len(absent):6,d} {'(few)':>30s}")
        context_results.append(entry)

    # Summaries
    dir_sig = sum(1 for r in direct_results if r.get("significant") and r.get("delta", 0) > 0)
    ctx_sig = sum(1 for r in context_results if r.get("significant") and r.get("delta", 0) > 0)
    dir_tested = sum(1 for r in direct_results if "significant" in r)
    ctx_tested = sum(1 for r in context_results if "significant" in r)
    print(f"\n    Direct: {dir_sig}/{dir_tested} significantly more toxic")
    print(f"    Context: {ctx_sig}/{ctx_tested} significantly predict toxic windows")

    return {
        "streamer": name,
        "spam": {"total": spam["total"], "spam": spam["spam"], "spam_pct": spam["spam_pct"]},
        "contagion_original": cg_orig,
        "contagion_deduped": cg_dedup,
        "deduped_attr_stats": attr_stats,
        "temporal": temporal,
        "mixed_vs_text": mixed_vs_text,
        "top_emotes_direct": direct_results,
        "top_emotes_context": context_results,
        "emote_summary": {"direct_sig": dir_sig, "direct_tested": dir_tested,
                          "context_sig": ctx_sig, "context_tested": ctx_tested},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scored", "-s", required=True)
    parser.add_argument("--chat", "-c", required=True)
    args = parser.parse_args()

    scored_dir = Path(args.scored)
    chat_dir = Path(args.chat)

    print("=" * 60)
    print("  SPAM + EMOTE + TEMPORAL ANALYSIS")
    print("=" * 60)

    all_results = {}
    for sdir in sorted(scored_dir.iterdir()):
        if not sdir.is_dir():
            continue
        name = sdir.name
        scored_path = sdir / "scored_messages.csv"
        chat_folder = chat_dir / name
        if not scored_path.exists() or not chat_folder.is_dir():
            continue
        result = process_streamer(name, chat_folder, scored_path)
        all_results[name] = result
        out_path = sdir / "emote_clean_analysis.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\n  → {out_path}")

    if len(all_results) > 1:
        print(f"\n{'='*60}")
        print(f"  CROSS-STREAMER")
        print(f"{'='*60}")

        print(f"\n  SPAM + CONTAGION:")
        print(f"  {'Streamer':15s} {'Spam%':>6s} {'Orig':>6s} {'Dedup':>6s} {'Δ':>7s}")
        print(f"  {'-'*45}")
        for name, r in sorted(all_results.items()):
            o = r["contagion_original"].get("ratio", "–")
            d = r["contagion_deduped"].get("ratio", "–")
            delta = f"{d-o:+.3f}" if isinstance(o, float) and isinstance(d, float) else "–"
            print(f"  {name:15s} {r['spam']['spam_pct']:5.1f}% {o:>6} {d:>6} {delta:>7}")

        print(f"\n  MIXED vs TEXT:")
        print(f"  {'Streamer':15s} {'Text':>7s} {'Mixed':>7s} {'Δ%':>7s} {'Sig':>5s}")
        print(f"  {'-'*45}")
        for name, r in sorted(all_results.items()):
            m = r["mixed_vs_text"]
            sig = "YES" if m.get("significant") else "no"
            print(f"  {name:15s} {m.get('text_mean','–'):>7} {m.get('mixed_mean','–'):>7} "
                  f"{m.get('mixed_more_toxic_pct','–'):>+6}% {sig:>5s}")

        print(f"\n  EMOTE SIGNIFICANCE:")
        print(f"  {'Streamer':15s} {'Dir Sig':>8s} {'Ctx Sig':>8s}")
        print(f"  {'-'*35}")
        for name, r in sorted(all_results.items()):
            s = r["emote_summary"]
            print(f"  {name:15s} {s['direct_sig']}/{s['direct_tested']:>4} {s['context_sig']}/{s['context_tested']:>4}")

    combined = scored_dir / "emote_clean_combined.json"
    with open(combined, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\n  → {combined}")


if __name__ == "__main__":
    main()