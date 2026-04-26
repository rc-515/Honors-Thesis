#!/usr/bin/env python3
"""
Toxicity Distribution Visualization
=====================================
Creates publication-quality violin/ridge plots showing the full
toxicity score distribution for each streamer.

Install:
    pip install matplotlib seaborn pandas numpy

Usage:
    python plot_distributions.py --input master_results/ --output plots/

    Optionally filter to only messages above a minimum score:
    python plot_distributions.py --input master_results/ --output plots/ --min-score 0.01
"""

import csv
import sys
import argparse
import random
from pathlib import Path
from collections import defaultdict

try:
    import matplotlib
    matplotlib.use('Agg')  # non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker
    import numpy as np
except ImportError:
    print("ERROR: pip install matplotlib numpy")
    sys.exit(1)

try:
    import seaborn as sns
    HAS_SEABORN = True
except ImportError:
    HAS_SEABORN = False
    print("WARNING: seaborn not found, using matplotlib only. pip install seaborn for better plots")


ATTRS = ["TOXICITY", "INSULT", "PROFANITY", "IDENTITY_ATTACK", "THREAT"]
ATTR_COLORS = {
    "TOXICITY": "#ff4d6a",
    "INSULT": "#4dd0e1",
    "PROFANITY": "#ffd740",
    "IDENTITY_ATTACK": "#b388ff",
    "THREAT": "#69f0ae",
}

# Dark theme matching your dashboard
DARK_BG = "#0c0e13"
DARK_CARD = "#14161d"
DARK_TEXT = "#e2e4ea"
DARK_GRID = "#2a2d3a"
DARK_MUTED = "#7a7e8f"

STREAMER_COLORS = {
    "clav": "#ff4d6a",
    "hstikkytokky": "#ffd740",
    "n3on": "#b388ff",
    "asmon": "#4dd0e1",
    "adin": "#69f0ae",
}

# Order from most to least toxic
STREAMER_ORDER = ["clav", "hstikkytokky", "n3on", "asmon", "adin"]


def apply_dark_theme():
    plt.rcParams.update({
        'figure.facecolor': DARK_BG,
        'axes.facecolor': DARK_CARD,
        'axes.edgecolor': DARK_GRID,
        'axes.labelcolor': DARK_TEXT,
        'text.color': DARK_TEXT,
        'xtick.color': DARK_MUTED,
        'ytick.color': DARK_MUTED,
        'grid.color': DARK_GRID,
        'grid.alpha': 0.3,
        'font.family': 'sans-serif',
        'font.size': 11,
    })


def load_scores(master_dir, max_per_streamer=500000):
    """Load TOXICITY scores from each streamer's scored_messages.csv."""
    data = {}
    root = Path(master_dir)

    for sdir in sorted(root.iterdir()):
        if not sdir.is_dir():
            continue
        csv_path = sdir / "scored_messages.csv"
        if not csv_path.exists():
            continue

        name = sdir.name
        scores = {attr: [] for attr in ATTRS}
        n = 0

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                for attr in ATTRS:
                    val = row.get(attr)
                    if val:
                        try:
                            scores[attr].append(float(val))
                        except:
                            pass
                n += 1
                if n >= max_per_streamer:
                    break

        if scores["TOXICITY"]:
            data[name] = scores
            print(f"  {name}: {len(scores['TOXICITY']):,} scores loaded")

    return data


def plot_violin_comparison(data, output_dir, min_score=0.0):
    """
    Main violin plot: toxicity distribution per streamer.
    Shows full distribution shape, not just summary stats.
    """
    apply_dark_theme()

    # Order streamers
    ordered = [s for s in STREAMER_ORDER if s in data]
    if not ordered:
        ordered = sorted(data.keys())

    fig, ax = plt.subplots(figsize=(14, 7))

    positions = list(range(len(ordered)))
    violins_data = []

    for i, name in enumerate(ordered):
        scores = [s for s in data[name]["TOXICITY"] if s >= min_score]
        # Sample if too large (violin plots choke on millions of points)
        if len(scores) > 100000:
            scores = random.sample(scores, 100000)
        violins_data.append(scores)

    parts = ax.violinplot(violins_data, positions=positions, showmeans=False,
                          showmedians=False, showextrema=False)

    for i, pc in enumerate(parts['bodies']):
        name = ordered[i]
        color = STREAMER_COLORS.get(name, "#ffffff")
        pc.set_facecolor(color)
        pc.set_edgecolor(color)
        pc.set_alpha(0.7)

    # Add boxplot inside
    bp = ax.boxplot(violins_data, positions=positions, widths=0.08,
                    patch_artist=True, showfliers=False, zorder=3)
    for element in ['boxes', 'whiskers', 'caps']:
        plt.setp(bp[element], color=DARK_TEXT, linewidth=0.8)
    plt.setp(bp['medians'], color='#ffffff', linewidth=1.5)
    for patch in bp['boxes']:
        patch.set_facecolor(DARK_CARD)

    # Add mean markers
    for i, scores in enumerate(violins_data):
        mean_val = np.mean(scores)
        ax.plot(i, mean_val, 'D', color='white', markersize=5, zorder=4)

    # Labels
    ax.set_xticks(positions)
    ax.set_xticklabels([f"{s}\n({len(violins_data[i]):,} msgs)" for i, s in enumerate(ordered)],
                       fontsize=12, fontweight='bold')
    ax.set_ylabel("Toxicity score", fontsize=13)
    ax.set_title("Toxicity score distribution by streamer", fontsize=16, fontweight='bold', pad=15)

    # Reference lines
    for thresh, label, ls in [(0.5, "0.5 threshold", "--"), (0.7, "0.7 threshold", ":")]:
        ax.axhline(y=thresh, color=DARK_MUTED, linestyle=ls, linewidth=0.8, alpha=0.6)
        ax.text(len(ordered) - 0.5, thresh + 0.01, label, fontsize=9, color=DARK_MUTED,
                ha='right', va='bottom')

    ax.set_ylim(-0.02, 1.02)
    ax.grid(axis='y', alpha=0.15)

    plt.tight_layout()
    path = output_dir / "toxicity_violin_comparison.png"
    fig.savefig(path, dpi=200, bbox_inches='tight', facecolor=DARK_BG)
    plt.close()
    print(f"  → {path}")


def plot_ridge(data, output_dir, min_score=0.0):
    """
    Ridge plot (joy plot): overlapping density curves stacked vertically.
    More dramatic visualization of the distribution differences.
    """
    apply_dark_theme()

    ordered = [s for s in STREAMER_ORDER if s in data]
    if not ordered:
        ordered = sorted(data.keys())

    fig, axes = plt.subplots(len(ordered), 1, figsize=(14, 2.2 * len(ordered)),
                             sharex=True)
    if len(ordered) == 1:
        axes = [axes]

    for i, name in enumerate(ordered):
        ax = axes[i]
        scores = [s for s in data[name]["TOXICITY"] if s >= min_score]
        if len(scores) > 200000:
            scores = random.sample(scores, 200000)

        color = STREAMER_COLORS.get(name, "#ffffff")

        # KDE using numpy histogram as approximation
        bins = np.linspace(0, 1, 200)
        hist, edges = np.histogram(scores, bins=bins, density=True)
        centers = (edges[:-1] + edges[1:]) / 2

        # Smooth with rolling average
        kernel_size = 5
        kernel = np.ones(kernel_size) / kernel_size
        smooth = np.convolve(hist, kernel, mode='same')

        ax.fill_between(centers, smooth, alpha=0.6, color=color)
        ax.plot(centers, smooth, color=color, linewidth=1.5)

        # Reference lines
        ax.axvline(x=0.5, color=DARK_MUTED, linestyle='--', linewidth=0.6, alpha=0.5)
        ax.axvline(x=0.7, color=DARK_MUTED, linestyle=':', linewidth=0.6, alpha=0.5)

        # Mean line
        mean_val = np.mean(scores)
        ax.axvline(x=mean_val, color='white', linewidth=1.2, alpha=0.8)

        # Label
        n_above_05 = sum(1 for s in scores if s > 0.5) / len(scores) * 100
        ax.text(0.02, 0.85, f"{name}", transform=ax.transAxes,
                fontsize=13, fontweight='bold', color=color, va='top')
        ax.text(0.02, 0.55, f"mean={mean_val:.3f}  |  {n_above_05:.1f}% above 0.5",
                transform=ax.transAxes, fontsize=9, color=DARK_MUTED, va='top')

        ax.set_yticks([])
        ax.set_ylabel("")
        ax.set_facecolor(DARK_BG)
        ax.spines['left'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['top'].set_visible(False)
        if i < len(ordered) - 1:
            ax.spines['bottom'].set_visible(False)
            ax.tick_params(bottom=False)

    axes[-1].set_xlabel("Toxicity score", fontsize=13)
    axes[-1].set_xlim(0, 1)

    fig.suptitle("Toxicity distribution by streamer community",
                 fontsize=16, fontweight='bold', y=1.01)

    plt.tight_layout()
    path = output_dir / "toxicity_ridge_comparison.png"
    fig.savefig(path, dpi=200, bbox_inches='tight', facecolor=DARK_BG)
    plt.close()
    print(f"  → {path}")


def plot_multi_attribute_violins(data, output_dir, min_score=0.0):
    """
    Grid of violin plots: one column per attribute, one row per streamer.
    Shows how the communities differ across toxicity dimensions.
    """
    apply_dark_theme()

    ordered = [s for s in STREAMER_ORDER if s in data]
    attrs_to_plot = ["TOXICITY", "INSULT", "PROFANITY", "IDENTITY_ATTACK", "THREAT"]

    fig, axes = plt.subplots(1, len(attrs_to_plot), figsize=(18, 6), sharey=True)

    for col, attr in enumerate(attrs_to_plot):
        ax = axes[col]
        vdata = []
        for name in ordered:
            scores = [s for s in data[name].get(attr, []) if s >= min_score]
            if len(scores) > 50000:
                scores = random.sample(scores, 50000)
            vdata.append(scores)

        if not any(vdata):
            continue

        parts = ax.violinplot(vdata, positions=range(len(ordered)),
                              showmeans=False, showmedians=False, showextrema=False)

        for i, pc in enumerate(parts['bodies']):
            name = ordered[i]
            pc.set_facecolor(STREAMER_COLORS.get(name, "#fff"))
            pc.set_edgecolor(STREAMER_COLORS.get(name, "#fff"))
            pc.set_alpha(0.65)

        # Means
        for i, scores in enumerate(vdata):
            if scores:
                ax.plot(i, np.mean(scores), 'D', color='white', markersize=4, zorder=4)

        ax.set_xticks(range(len(ordered)))
        ax.set_xticklabels([s[:6] for s in ordered], fontsize=9, rotation=30)
        ax.set_title(attr.replace("_", " ").title(), fontsize=11, fontweight='bold',
                     color=ATTR_COLORS.get(attr, DARK_TEXT))
        ax.grid(axis='y', alpha=0.15)
        ax.set_ylim(-0.02, 1.02)

    axes[0].set_ylabel("Score", fontsize=12)

    fig.suptitle("Score distributions across all attributes and streamers",
                 fontsize=15, fontweight='bold')
    plt.tight_layout()
    path = output_dir / "multi_attribute_violins.png"
    fig.savefig(path, dpi=200, bbox_inches='tight', facecolor=DARK_BG)
    plt.close()
    print(f"  → {path}")


def plot_threshold_breakdown(data, output_dir):
    """
    Stacked bar chart showing what proportion of messages fall in
    each toxicity band: <0.1, 0.1-0.3, 0.3-0.5, 0.5-0.7, 0.7-0.9, 0.9+
    """
    apply_dark_theme()

    ordered = [s for s in STREAMER_ORDER if s in data]
    bands = [(0, 0.1), (0.1, 0.3), (0.3, 0.5), (0.5, 0.7), (0.7, 0.9), (0.9, 1.01)]
    band_labels = ["<0.1", "0.1–0.3", "0.3–0.5", "0.5–0.7", "0.7–0.9", "0.9+"]
    band_colors = ["#1a1d27", "#2a2d3a", "#ffd74060", "#ffd740", "#ff4d6a", "#ff1744"]

    fig, ax = plt.subplots(figsize=(12, 6))

    band_data = {label: [] for label in band_labels}
    for name in ordered:
        scores = data[name]["TOXICITY"]
        n = len(scores)
        for (lo, hi), label in zip(bands, band_labels):
            count = sum(1 for s in scores if lo <= s < hi)
            band_data[label].append(count / n * 100)

    x = np.arange(len(ordered))
    width = 0.6
    bottom = np.zeros(len(ordered))

    for label, color in zip(band_labels, band_colors):
        vals = band_data[label]
        bars = ax.bar(x, vals, width, bottom=bottom, label=label,
                      color=color, edgecolor=DARK_CARD, linewidth=0.5)
        # Add % labels for significant bands
        for i, v in enumerate(vals):
            if v > 4:
                ax.text(i, bottom[i] + v / 2, f"{v:.1f}%",
                        ha='center', va='center', fontsize=8, color=DARK_TEXT)
        bottom += vals

    ax.set_xticks(x)
    ax.set_xticklabels(ordered, fontsize=12, fontweight='bold')
    ax.set_ylabel("% of messages", fontsize=13)
    ax.set_title("Distribution of toxicity scores by band", fontsize=15, fontweight='bold', pad=15)
    ax.legend(loc='upper right', fontsize=9, facecolor=DARK_CARD, edgecolor=DARK_GRID)
    ax.set_ylim(0, 105)

    plt.tight_layout()
    path = output_dir / "toxicity_band_breakdown.png"
    fig.savefig(path, dpi=200, bbox_inches='tight', facecolor=DARK_BG)
    plt.close()
    print(f"  → {path}")


def plot_cumulative(data, output_dir):
    """
    Cumulative distribution (CDF) — shows what % of messages are
    below each toxicity score. Lines further right = more toxic community.
    """
    apply_dark_theme()

    ordered = [s for s in STREAMER_ORDER if s in data]

    fig, ax = plt.subplots(figsize=(12, 7))

    for name in ordered:
        scores = sorted(data[name]["TOXICITY"])
        if len(scores) > 200000:
            scores = sorted(random.sample(data[name]["TOXICITY"], 200000))
        n = len(scores)
        y = np.arange(1, n + 1) / n * 100
        # Subsample for plotting
        step = max(1, n // 2000)
        ax.plot(scores[::step], y[::step],
                color=STREAMER_COLORS.get(name, "#fff"),
                linewidth=2.5, label=name, alpha=0.85)

    ax.axvline(x=0.5, color=DARK_MUTED, linestyle='--', linewidth=0.8, alpha=0.5)
    ax.axvline(x=0.7, color=DARK_MUTED, linestyle=':', linewidth=0.8, alpha=0.5)
    ax.text(0.51, 5, "0.5", fontsize=9, color=DARK_MUTED)
    ax.text(0.71, 5, "0.7", fontsize=9, color=DARK_MUTED)

    ax.set_xlabel("Toxicity score", fontsize=13)
    ax.set_ylabel("Cumulative % of messages", fontsize=13)
    ax.set_title("Cumulative toxicity distribution by streamer", fontsize=15, fontweight='bold', pad=15)
    ax.legend(fontsize=11, facecolor=DARK_CARD, edgecolor=DARK_GRID, loc='lower right')
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 102)
    ax.grid(axis='both', alpha=0.15)

    plt.tight_layout()
    path = output_dir / "toxicity_cumulative_distribution.png"
    fig.savefig(path, dpi=200, bbox_inches='tight', facecolor=DARK_BG)
    plt.close()
    print(f"  → {path}")


def main():
    parser = argparse.ArgumentParser(description="Plot toxicity distributions across streamers")
    parser.add_argument("--input", "-i", required=True, help="master_results/ directory")
    parser.add_argument("--output", "-o", default="plots", help="Output directory for images")
    parser.add_argument("--min-score", type=float, default=0.0,
                        help="Minimum score to include (0.01 filters out near-zero noise)")
    parser.add_argument("--max-per-streamer", type=int, default=500000,
                        help="Max messages to load per streamer (default 500k)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")

    args = parser.parse_args()
    random.seed(args.seed)
    np.random.seed(args.seed)

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("  TOXICITY DISTRIBUTION PLOTS")
    print("=" * 60)

    print("\n  Loading scores...")
    data = load_scores(args.input, max_per_streamer=args.max_per_streamer)

    if not data:
        print("  [ERROR] No scored data found")
        sys.exit(1)

    print(f"\n  Generating plots (min_score={args.min_score})...")

    plot_violin_comparison(data, out, min_score=args.min_score)
    plot_ridge(data, out, min_score=args.min_score)
    plot_multi_attribute_violins(data, out, min_score=args.min_score)
    plot_threshold_breakdown(data, out)
    plot_cumulative(data, out)

    # Also generate versions filtering out near-zero scores
    # (more useful for seeing the toxic tail)
    if args.min_score == 0:
        print(f"\n  Generating filtered versions (min_score=0.01)...")
        filtered_out = out / "filtered"
        filtered_out.mkdir(exist_ok=True)
        plot_violin_comparison(data, filtered_out, min_score=0.01)
        plot_ridge(data, filtered_out, min_score=0.01)

    print(f"\n{'='*60}")
    print(f"  All plots saved to {out}/")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
