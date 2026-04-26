# Far-Right Livestream Chat Toxicity Analysis

Replication code for a study of toxicity, engagement, and community dynamics in far-right-adjacent livestream communities on Kick.com (and Twitch). 


## Data

This repository contains only the analysis code. The raw data required to replicate consists of:

```
chat_logs/
    {streamer_name}/
        stream_YYYY-MM-DD.json     # Kick.com chat logs
stream_viewership/
    {streamer_name}/
        viewership_YYYY-MM-DD.csv  # 5-minute viewership snapshots
twitch_streams/
    {streamer_name}/
        stream_YYYY-MM-DD.csv      # Twitch chat logs (time, user_name, user_color, message)
```

The Kick chats were downloaded using [Kicklet](https://kicklet.app/chat-downloader), and the viewership was downloaded using [Streams Charts](https://streamscharts.com/overview?platform=kick).

Kick.com chat JSON format:
```json
[{"content": "message", "createdAt": "2026-03-01T21:31:56Z", "userId": "12345", "username": "user"}]
```

Viewership CSV format:
```
Date Time, Viewers, Followers gain
Mar 06, 2026 00:10, 12227, 3
```

> **Note:** Raw chat logs are not included in this repository. They may contain identifiable usernames and are subject to platform terms of service.

---

## Setup

```bash
pip install detoxify transformers torch scipy matplotlib seaborn numpy pandas google-generativeai
```

Python 3.9+ required. GPU recommended for scoring large corpora (5M+ messages).

---

## Pipeline

Run scripts in this order:

### 1. Score Kick.com chat messages

```bash
python master_pipeline.py \
    --input chat_logs/ \
    --output master_results/ \
    --model unbiased \
    --score-all
```

Scores all text messages with Detoxify (`unbiased` model). Also runs: contagion analysis, temporal patterns, first-message analysis (new users only), burst detection, user acceleration, and message concentration. Outputs per-streamer `scored_messages.csv` and `analysis.json`.

**Options:**
- `--model` — `original`, `unbiased` (default), `original-small`, `unbiased-small`
- `--batch-size` — default 128, increase for GPU
- `--score-all` — score every message (default: top users only)

---

### 2. Score Twitch chat messages

```bash
python twitch_score.py \
    --input twitch_streams/ \
    --output twitch_results/
```

Handles Twitch-specific filtering: emote-only messages (200+ known global/BTTV/FFZ/7TV emotes), bot accounts (Nightbot, StreamElements, etc.), and commands (`!command`).

**Options:**
- `--emote-file my_emotes.txt` — add channel-specific emotes (one per line)
- `--bot-file my_bots.txt` — add channel-specific bots

---

### 3. Viewership × toxicity analysis

```bash
python viewership_analysis.py \
    --chat chat_logs/ \
    --viewership stream_viewership/ \
    --scored master_results/ \
    --output viewership_results/
```

Merges 5-minute viewership snapshots with chat data. Computes: toxicity × viewership correlation (overall + per-attribute), viewer departure after toxic bursts, participation rate, follower gain × toxicity, raid detection, stream warmup (Q1→Q4 toxicity), and per-attribute (INSULT, IDENTITY_ATTACK, THREAT) viewership correlations.

---

### 4. Spam, emote, and temporal analysis

```bash
python emote_clean.py \
    --scored master_results/ \
    --chat chat_logs/
```

Combined analysis: spam detection and deduplication, contagion recompute (original vs deduped), deduped attribute stats, temporal patterns (toxicity by hour and day of week), mixed vs text-only toxicity comparison, and top-30 emote toxicity analysis (popularity-first, direct + context approaches).

---

### 5. Multi-model validation

```bash
# Detoxify + RoBERTa + Gemini:
python multi_model_compare.py \
    --input master_results/streamer/scored_messages.csv \
    --gemini-key YOUR_KEY \
    --n 500

# Detoxify + RoBERTa only:
python multi_model_compare.py \
    --input master_results/streamer/scored_messages.csv \
    --n 500
```

Scores a random sample with up to three independent classifiers and computes pairwise Pearson/Spearman correlations and threshold agreement (0.3, 0.5, 0.7). Models: Detoxify (Jigsaw-trained), RoBERTa dynabench-r4 (adversarial hate speech), Gemini 2.5 Flash (LLM-as-judge).

---

### 6. RoBERTa hate speech: new users and viewership

```bash
python roberta_analysis.py \
    --roberta roberta_results/ \
    --chat chat_logs/ \
    --viewership viewership_results/ \
    --output roberta_analysis/
```

Requires pre-scored `roberta_results/{streamer}/scored_messages.csv`. Tests: do new users (joined after first 25% of data) have lower hate speech scores? Are new users' first messages less hateful than their overall average? Does hate speech increase with viewership?

---

### 7. New user and power user profiles

```bash
python user_profiles.py \
    --scored master_results/ \
    --chat chat_logs/
```

Computes new user profiles (joined after first 25% cutoff): emote usage rate, emote adoption over time (do they become more emote-fluent?), toxicity trajectory, dominant toxicity subtype. Also computes power user typology: top 50 users by message count, subtype distribution (insult-dominant, profanity-dominant, identity-attack-dominant, threat-dominant).

---

### 8. Toxic span finder

```bash
python toxic_spans.py --input master_results/
```

Finds the five highest-toxicity 50-message windows per streamer, with spam removed. Reports mean toxicity, duration, stream number, time elapsed since stream start, unique users, dominant attribute, and the five most toxic messages in each span.

---

### 9. Visualizations

```bash
python plot_distributions.py \
    --input master_results/ \
    --output plots/
```

Generates: toxicity violin plots per streamer, ridge/density plots, cumulative distribution (CDF), stacked bar by toxicity band, and multi-attribute violin grid. All in a dark theme. Also generates filtered versions (`plots/filtered/`) excluding near-zero scores to better visualize the toxic tail.

---

### 10. Stream hours

```bash
python stream_hours.py --input chat_logs/
```

Estimates total footage hours per streamer from first and last message timestamps in each JSON file.

---

## Output Structure

```
master_results/
    {streamer}/
        scored_messages.csv      # All scored messages with 6 attribute scores
        analysis.json            # Full analysis: contagion, temporal, first-message,
                                 #   acceleration, concentration, burst detection
        user_profiles.json       # New user + power user profiles
        emote_clean_analysis.json
viewership_results/
    {streamer}/
        windowed_data.csv        # 5-min windows with viewers + toxicity
        viewership_analysis.json
    cross_streamer_viewership.json
twitch_results/
    {streamer}/
        scored_messages.csv
        analysis.json
roberta_analysis/
    {streamer}/
        roberta_analysis.json
    roberta_combined.json
plots/
    toxicity_violin_comparison.png
    toxicity_ridge_comparison.png
    toxicity_cumulative_distribution.png
    toxicity_band_breakdown.png
    multi_attribute_violins.png
```

---

## Key Findings

- **No engagement→toxicity pipeline.** Acceleration (increasing message frequency) does not predict increasing toxicity (r = −0.06, p = 0.52, n=138 for primary streamer; replicated across all five communities). Users who become more active are the *least* likely to escalate in toxicity.
- **Selection model fits better than radicalization.** New users arrive at roughly the toxicity level they will maintain. First-message toxicity ≈ overall average across all five communities.
- **Participation rates are extremely low.** Only 1–2.7% of viewers chat at any given time. The "toxic community" analyzed represents a small vocal minority of the actual audience.
- **Toxicity contagion is real but short-term.** After a toxic message, the next five messages are 18–28% more toxic (post-spam-dedup, significant across all five streamers). This is short-term cascading, not long-term drift.
- **Viewers do not leave after toxic moments.** Zero of five streamers show significant viewer departure following toxic windows.
- **Community structure is highly concentrated.** The top 1% of users produce approximately 30% of all messages.
- **Cross-model validation.** Detoxify and Gemini 2.5 Flash show substantial agreement (Spearman ρ = 0.56, n=500).

---

## Models Used

| Model | Type | Purpose |
|---|---|---|
| [Detoxify (unbiased)](https://github.com/unitaryai/detoxify) | Fine-tuned RoBERTa | Primary scorer — 6 toxicity attributes |
| [RoBERTa dynabench-r4](https://huggingface.co/facebook/roberta-hate-speech-dynabench-r4-target) | Fine-tuned RoBERTa | Hate speech validation |
| Gemini 2.5 Flash | LLM | Cross-paradigm validation |

---

## Thesis

The Thesis discussing the results of this project is accessible through [Wesleyan's Special Collections & Archives](https://digitalcollections.wesleyan.edu/islandora/object/wesleyanct-etd_hon_theses?).

---

## Notes

- All scoring uses Detoxify's `unbiased` model, which corrects for identity-term bias present in the `original` model.
- Spam detection flags same-user repeated messages and messages appearing 3+ times in a 10-message window. All contagion results are reported post-deduplication as primary findings.
- First-message analysis only includes users whose first message appeared after the first 25% of the data's time range, excluding day-one users whose "first" message is an artifact of data collection start.
- Stream segmentation uses a 1-hour gap threshold between messages to identify individual streams.
- Emote-only messages (~35% of all Kick messages) are excluded from scoring but analyzed separately through time-window context analysis.