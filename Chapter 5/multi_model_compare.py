#!/usr/bin/env python3
"""
Multi-Model Toxicity Comparison: Detoxify × RoBERTa × Gemini
===============================================================
Scores a random sample of messages with three independent models,
computes inter-model correlations and threshold agreement.

Models:
  1. Detoxify (unbiased) — Jigsaw-trained, local
  2. RoBERTa dynabench r4 — adversarial hate speech, local
  3. Gemini 2.5 Flash — LLM-as-judge, API

Usage:
    python multi_model_compare.py \\
        --input master_results/asmon/scored_messages.csv \\
        --gemini-key YOUR_KEY \\
        --n 500

    Or skip Gemini:
    python multi_model_compare.py --input master_results/asmon/scored_messages.csv --n 500

Install:
    pip install detoxify transformers torch google-generativeai scipy
"""

import csv
import json
import sys
import random
import argparse
import statistics
import time
from pathlib import Path

try:
    from scipy import stats as sp
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


def load_sample(path, n=500, seed=42):
    """Load a random sample of scored messages."""
    random.seed(seed)
    with open(path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    # Filter to messages with actual text
    rows = [r for r in rows if r.get("clean_text", r.get("content", "")).strip()]
    if len(rows) > n:
        rows = random.sample(rows, n)
    print(f"  Sampled {len(rows)} messages")
    return rows


# ═══════════════════════════════════════════════════════════════
#  MODEL 1: DETOXIFY
# ═══════════════════════════════════════════════════════════════

def score_detoxify(texts, model_name="unbiased", batch_size=64):
    print(f"\n  [DETOXIFY ({model_name})]")
    from detoxify import Detoxify
    model = Detoxify(model_name)
    scores = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        result = model.predict(batch)
        for j in range(len(batch)):
            scores.append(result["toxicity"][j])
        print(f"    {min(i + batch_size, len(texts))}/{len(texts)}")
    print(f"    Mean: {statistics.mean(scores):.4f}")
    return scores


# ═══════════════════════════════════════════════════════════════
#  MODEL 2: ROBERTA DYNABENCH
# ═══════════════════════════════════════════════════════════════

def score_roberta(texts, batch_size=32):
    print(f"\n  [ROBERTA dynabench-r4]")
    from transformers import pipeline
    pipe = pipeline("text-classification",
                    model="facebook/roberta-hate-speech-dynabench-r4-target",
                    top_k=None, truncation=True, max_length=512)
    scores = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        results = pipe(batch)
        for result in results:
            # result is a list of {label, score} dicts
            label_scores = {r["label"]: r["score"] for r in result}
            # "hate" label score = hate speech probability
            hate = label_scores.get("hate", label_scores.get("LABEL_1", 0))
            scores.append(hate)
        print(f"    {min(i + batch_size, len(texts))}/{len(texts)}")
    print(f"    Mean: {statistics.mean(scores):.4f}")
    return scores


# ═══════════════════════════════════════════════════════════════
#  MODEL 3: GEMINI
# ═══════════════════════════════════════════════════════════════

def score_gemini(texts, api_key, model_name="gemini-2.5-flash", batch_size=10,
                 rate_limit_delay=1.0):
    print(f"\n  [GEMINI ({model_name})]")
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)

    prompt_template = """Rate the toxicity of each message below on a scale from 0.0 (completely harmless) to 1.0 (extremely toxic/hateful).

Consider: hate speech, identity attacks, threats, severe insults, slurs, dehumanization.
Casual profanity without a target should score lower than directed hate.

Return ONLY a JSON array of numbers, one per message. No other text.

Messages:
{messages}"""

    scores = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        numbered = "\n".join(f"{j+1}. {t[:200]}" for j, t in enumerate(batch))
        prompt = prompt_template.format(messages=numbered)

        retries = 3
        for attempt in range(retries):
            try:
                response = model.generate_content(prompt)
                raw = response.text.strip()
                # Clean response
                raw = raw.replace("```json", "").replace("```", "").strip()
                parsed = json.loads(raw)
                if isinstance(parsed, list) and len(parsed) == len(batch):
                    scores.extend([min(1.0, max(0.0, float(s))) for s in parsed])
                    break
                else:
                    print(f"    Warning: expected {len(batch)} scores, got {len(parsed) if isinstance(parsed, list) else 'non-list'}")
                    # Pad or truncate
                    if isinstance(parsed, list):
                        parsed = parsed[:len(batch)]
                        while len(parsed) < len(batch):
                            parsed.append(0.5)  # default
                        scores.extend([min(1.0, max(0.0, float(s))) for s in parsed])
                        break
            except Exception as e:
                if attempt < retries - 1:
                    print(f"    Retry {attempt+1}: {e}")
                    time.sleep(rate_limit_delay * (attempt + 1))
                else:
                    print(f"    Failed after {retries} attempts, filling with NaN")
                    scores.extend([None] * len(batch))

        done = min(i + batch_size, len(texts))
        if done % (batch_size * 5) == 0 or done >= len(texts):
            valid = [s for s in scores if s is not None]
            print(f"    {done}/{len(texts)} (mean so far: {statistics.mean(valid):.4f})" if valid else f"    {done}/{len(texts)}")

        time.sleep(rate_limit_delay)

    valid = [s for s in scores if s is not None]
    if valid:
        print(f"    Mean: {statistics.mean(valid):.4f} ({len(valid)} valid of {len(scores)})")
    return scores


# ═══════════════════════════════════════════════════════════════
#  COMPARISON
# ═══════════════════════════════════════════════════════════════

def compare_models(model_scores: dict, thresholds=[0.3, 0.5, 0.7]):
    """Compute inter-model correlations and threshold agreement."""
    results = {"models": list(model_scores.keys())}
    names = list(model_scores.keys())

    # Pairwise correlations
    correlations = {}
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a_name, b_name = names[i], names[j]
            a_scores, b_scores = model_scores[a_name], model_scores[b_name]

            # Filter to indices where both have valid scores
            pairs = [(a, b) for a, b in zip(a_scores, b_scores)
                     if a is not None and b is not None]
            if len(pairs) < 20:
                continue

            a_vals, b_vals = zip(*pairs)
            label = f"{a_name} vs {b_name}"
            corr = {"n": len(pairs)}

            if HAS_SCIPY:
                pr, pp = sp.pearsonr(a_vals, b_vals)
                sr, spp = sp.spearmanr(a_vals, b_vals)
                corr.update({
                    "pearson_r": round(pr, 4), "pearson_p": round(pp, 8),
                    "spearman_r": round(sr, 4), "spearman_p": round(spp, 8),
                })
            correlations[label] = corr
    results["correlations"] = correlations

    # Threshold agreement
    agreement = {}
    for thresh in thresholds:
        for name, scores in model_scores.items():
            valid = [s for s in scores if s is not None]
            count = sum(1 for s in valid if s > thresh)
            agreement[f"{name}_above_{thresh}"] = {
                "count": count,
                "pct": round(count / max(len(valid), 1) * 100, 1),
            }
    results["threshold_agreement"] = agreement

    # Cross-model agreement at each threshold
    for thresh in thresholds:
        # How often do all models agree a message is toxic?
        all_agree = 0
        any_flags = 0
        n_valid = 0

        for idx in range(len(list(model_scores.values())[0])):
            vals = []
            for scores in model_scores.values():
                if idx < len(scores) and scores[idx] is not None:
                    vals.append(scores[idx])
            if len(vals) == len(model_scores):
                n_valid += 1
                flags = sum(1 for v in vals if v > thresh)
                if flags == len(vals):
                    all_agree += 1
                if flags > 0:
                    any_flags += 1

        if n_valid > 0:
            agreement[f"all_agree_above_{thresh}"] = {
                "count": all_agree, "pct": round(all_agree / n_valid * 100, 1),
                "any_flag": any_flags, "any_flag_pct": round(any_flags / n_valid * 100, 1),
                "n_valid": n_valid,
            }

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", "-i", required=True,
                        help="scored_messages.csv (or any CSV with text)")
    parser.add_argument("--n", type=int, default=500, help="Sample size")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--gemini-key", default=None, help="Gemini API key (omit to skip)")
    parser.add_argument("--output", "-o", default="model_comparison_results")
    parser.add_argument("--skip-detoxify", action="store_true")
    parser.add_argument("--skip-roberta", action="store_true")
    args = parser.parse_args()

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("  MULTI-MODEL TOXICITY COMPARISON")
    print("=" * 60)

    rows = load_sample(args.input, n=args.n, seed=args.seed)
    texts = [r.get("clean_text", r.get("content", "")).strip() for r in rows]

    model_scores = {}

    # Detoxify
    if not args.skip_detoxify:
        try:
            model_scores["Detoxify"] = score_detoxify(texts)
        except ImportError:
            print("  Detoxify not installed, skipping")
    else:
        # Use existing scores if available
        existing = []
        for r in rows:
            try:
                existing.append(float(r.get("TOXICITY", 0)))
            except:
                existing.append(None)
        if any(v is not None for v in existing):
            model_scores["Detoxify"] = existing
            print(f"\n  [DETOXIFY] Using existing scores from CSV")
            valid = [v for v in existing if v is not None]
            print(f"    Mean: {statistics.mean(valid):.4f}")

    # RoBERTa
    if not args.skip_roberta:
        try:
            model_scores["RoBERTa_dynabench"] = score_roberta(texts)
        except ImportError:
            print("  transformers not installed, skipping RoBERTa")
        except Exception as e:
            print(f"  RoBERTa error: {e}")

    # Gemini
    if args.gemini_key:
        try:
            model_scores["Gemini_Flash"] = score_gemini(texts, args.gemini_key)
        except ImportError:
            print("  google-generativeai not installed: pip install google-generativeai")
        except Exception as e:
            print(f"  Gemini error: {e}")
    else:
        print(f"\n  [GEMINI] Skipped (no --gemini-key)")

    if len(model_scores) < 2:
        print("\n  Need at least 2 models for comparison")
        sys.exit(1)

    # Compare
    print(f"\n{'='*60}")
    print(f"  COMPARISON ({len(model_scores)} models)")
    print(f"{'='*60}")

    results = compare_models(model_scores)

    # Print correlations
    print(f"\n  INTER-MODEL CORRELATIONS:")
    print(f"  {'Pair':40s} {'n':>6s} {'Pearson r':>10s} {'Spearman ρ':>11s}")
    print(f"  {'-'*70}")
    for label, corr in results["correlations"].items():
        print(f"  {label:40s} {corr['n']:6d} "
              f"{corr.get('pearson_r','–'):>10} {corr.get('spearman_r','–'):>11}")

    # Print threshold agreement
    print(f"\n  THRESHOLD AGREEMENT:")
    for thresh in [0.3, 0.5, 0.7]:
        print(f"\n    At {thresh}:")
        for name in model_scores:
            key = f"{name}_above_{thresh}"
            a = results["threshold_agreement"].get(key, {})
            print(f"      {name:25s} {a.get('count',0):5d} ({a.get('pct',0):.1f}%)")
        aa = results["threshold_agreement"].get(f"all_agree_above_{thresh}", {})
        if aa:
            print(f"      {'All models agree':25s} {aa['count']:5d} ({aa['pct']:.1f}%)")
            print(f"      {'Any model flags':25s} {aa['any_flag']:5d} ({aa['any_flag_pct']:.1f}%)")

    # Export per-message scores
    per_msg_path = out / "per_message_scores.csv"
    with open(per_msg_path, "w", newline="", encoding="utf-8") as f:
        fields = ["text"] + list(model_scores.keys())
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for i, text in enumerate(texts):
            row = {"text": text[:500]}
            for name, scores in model_scores.items():
                row[name] = round(scores[i], 4) if i < len(scores) and scores[i] is not None else ""
            w.writerow(row)
    print(f"\n  → {per_msg_path}")

    # Export summary
    summary_path = out / "model_comparison_stats.json"
    results["n_messages"] = len(texts)
    results["models_used"] = list(model_scores.keys())
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"  → {summary_path}")

    print(f"\n{'='*60}")
    print(f"  Done!")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()