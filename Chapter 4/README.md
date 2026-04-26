# Instagram Reels Algorithm Analysis

Replication code for a study of what content Instagram's Reels algorithm recommends to different user profiles, and how engagement behavior shapes those recommendations over time.

---

## Overview

The pipeline automates three stages:

1. **Engagement** — Actively likes and saves reels to signal preferences to the algorithm. This is optional, and in the thesis was only done before one instance of swiping and capturing reels.
2. **Swiping** — An Android device scrolls through Instagram Reels, captures URLs and screenshots of each reel seen.
3. **Downloading & Analysis** — Videos are downloaded and analyzed using Gemini 2.5 Flash across ~20 content dimensions (political leaning, gender targeting, extremism indicators, topic, etc.)

---

## Requirements

```bash
pip install appium-python-client faster-whisper opencv-python requests
```

- Python 3.9+
- [Appium](https://appium.io/) server running locally on port 4723
- Android device with ADB access and Instagram installed
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) installed and a valid `cookies.txt` for Instagram
- Gemini API key (for `analyze.py`)

> **Note:** `cookies.txt` can be downloaded from an internet browser like Edge. It contains the tokens authenticating a valid instagram login in that browser. 

You also must install the [Genymotion](https://www.genymotion.com/product-desktop/download/) app for desktop and initialize an Android device.

---

## Data

The pipeline produces the following directory structure:

```
logs/
    {account}/
        {account}_{session_number}_session.json        # Reel URLs + screenshots per session
        {account}_{session_number}_engagement_session.json  # Like/save logs per session
videos/
    {account}/
        {shortcode}.mp4     # Downloaded reel video
        {shortcode}.txt     # Instagram caption (if available)
processed_{account}.json    # Final analysis output (one entry per reel)
```

---

## Pipeline

Run scripts in this order:

### 1. Engage with Reels (`engaging.py`) *(optional)*

Scrolls through Reels and actively likes and saves (bookmarks on the account) each one, to train the algorithm toward a specific content profile.

```bash
python engaging.py <account> <session_number> --udid <device_udid>
```

> **Note:** `<account>` does not need to be an instagram username. For example, I had an account following far-right creators and simply labeled it "following". The important thing is that it is consistent between sessions.

**Example:**
```bash
python engaging.py following 1 --udid 192.168.1.100:5555
```

**Output:** `logs/{account}_{session_number}_engagement_session.json`

Each record contains:
```json
{
  "SESSION_ID": "user_a_1",
  "reel_index": 1,
  "timestamp_utc": "2026-04-01T14:10:00",
  "liked": true,
  "saved": true
}
```

**Config (edit at top of file):**
- `REELS_TO_ENGAGE` — Number of reels to like/save (default: 50)
- `WATCH_TIME` — Seconds spent on each reel before engaging (default: 10)

> Both scripts automatically skip ads (detected via "Ad", "Sponsored", "Install", "Shop", "Download" UI elements).

---

### 2. Capture Reels (`swiping.py`)

Scrolls through Instagram Reels on an Android device, records each reel's URL and a screenshot.

```bash
python swiping.py <account> <session_number> --udid <device_udid>
```

**Example:**
```bash
python swiping.py user_a 1 --udid 192.168.1.100:5555
```

**Arguments:**
- `account` — A label for the test account (e.g., `user_a`)
- `session_number` — Session identifier (e.g., `1`, `2`, `3`)
- `--udid` — Device UDID from `adb devices` (format: `XXX.XXX.XX.XXX:XXXX`)

**Output:** `logs/{account}_{session_number}_session.json`

Each record contains:
```json
{
  "SESSION_ID": "user_a_1",
  "reel_index": 1,
  "timestamp_utc": "2026-04-01T14:00:00",
  "reel_url": "https://www.instagram.com/reel/ABC123/",
  "screenshot_path": "logs/user_a_1_reel_1.png"
}
```

**Config (edit at top of file):**
- `REELS_TO_CAPTURE` — Number of reels to capture per session (default: 30)
- `WATCH_TIME` — Seconds spent watching each reel before swiping (default: 8)

---

### 3. Download Videos (`download.py`)

Downloads the reel videos captured during swiping sessions using `yt-dlp`.

```bash
python download.py <account>
```

**Example:**
```bash
python download.py following
```

Reads session logs from `logs/{account}_new/` and saves videos to `videos/{account}_new/` each as an mp4. Already-downloaded videos are skipped automatically. The videos are named whatever the video tag is, i.e. a video with the link `instagram.com/reel/ABC123/` becomes `ABC123.mp4`.

> **Note:** remember `<account>` must be the same as in script 2.

**Requirements:**
- `yt-dlp` installed
- `cookies.txt` in the working directory (exported from a logged-in Instagram browser session)

---

### 4. Analyze Reels (`analyze.py`)

Transcribes audio, extracts video frames, and sends each reel to Gemini 2.5 Flash for content analysis across ~20 dimensions.

```bash
python analyze.py <account> --api-key <your_gemini_api_key>
```

**Example:**
```bash
python analyze.py user_a --api-key AIza...
```

Reads session files from `logs/{account}/` and videos from `videos/{account}/`. Saves results incrementally to `processed_{account}.json` and supports resuming interrupted runs.

**Output:** `processed_{account}.json` — one entry per reel:

```json
{
  "session_file": "user_a_1_session.json",
  "device_id": "user_a_1",
  "reel_index": 1,
  "shortcode": "ABC123",
  "reel_url": "https://www.instagram.com/reel/ABC123/",
  "instagram_caption": "Caption text...",
  "spoken_transcript": "Transcribed audio...",
  "num_frames_sent": 5,
  "gemini_analysis": {
    "description": "A fitness influencer demonstrates a workout routine.",
    "gender_target": "men",
    "political_content": 0,
    "political_leaning": "none",
    "traditional_gender_roles": 0,
    "military_patriotic_law_enforcement": 0,
    "religion": 0,
    "edgy_humor": 0,
    "violence": 0,
    "guns_weapons": 0,
    "sexual_suggestive": 0,
    "rage_bait_outrage": 0,
    "conspiratorial": 0,
    "pseudoscientific": 0,
    "extreme": 0,
    "radical": 0,
    "discriminatory": 0,
    "incel-related": 0,
    "anti_woke_anti_progressive": 0,
    "masculinity_femininity_focus": "masculinity",
    "topic": "fitness",
    "notes": "Content focuses on male physique and strength training."
  }
}
```

**Analysis field definitions:**

| Field | Values | Description |
|---|---|---|
| `gender_target` | `men`, `women`, `neutral` | Apparent target audience by gender |
| `political_content` | 0/1 | Whether the reel contains political content |
| `political_leaning` | `left`, `right`, `center`, `none` | Overall ideological slant |
| `traditional_gender_roles` | 0/1 | Reinforces conventional gender expectations |
| `military_patriotic_law_enforcement` | 0/1 | Military, patriotic, or law enforcement themes |
| `religion` | 0/1 | Religious content |
| `edgy_humor` | 0/1 | Provocative or boundary-pushing comedy |
| `violence` | 0/1 | Violent content |
| `guns_weapons` | 0/1 | Firearms or weapons present |
| `sexual_suggestive` | 0/1 | Sexually suggestive content |
| `rage_bait_outrage` | 0/1 | Designed to provoke anger for engagement |
| `conspiratorial` | 0/1 | Propagates unverified conspiracy theories |
| `pseudoscientific` | 0/1 | False claims framed as science |
| `extreme` | 0/1 | Promotes violent ideologies or social disruption |
| `radical` | 0/1 | Encourages adoption of extreme ideologies |
| `discriminatory` | 0/1 | Expresses hatred toward out-groups |
| `incel-related` | 0/1 | Anti-feminist or anti-woman content |
| `anti_woke_anti_progressive` | 0/1 | Mocks or criticizes progressive social movements |
| `masculinity_femininity_focus` | `masculinity`, `femininity`, `none` | Whether content centers on gendered identity |
| `topic` | `politics`, `fitness`, `comedy`, `news`, `lifestyle`, `finance`, `sports`, `education`, `music`, `food`, `tech`, `religion`, `other` | Primary topic category |

**Config (edit at top of file):**
- `NUM_FRAMES` — Frames extracted per video for Gemini (default: 5)
- `MAX_RETRIES` — Retries on invalid Gemini responses (default: 5)
- Whisper model size: `base` (CPU, int8) — change in source for faster/larger models

---

## Notes

- Analysis results are saved after every reel, so interrupted runs can be safely resumed.
- Reels with invalid Gemini responses (missing fields, wrong types) are automatically retried up to `MAX_RETRIES` times.
- Non-reel URLs (photo posts, stories) are skipped during download.
- Audio transcription uses [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (`base` model). Videos without audio return an empty transcript gracefully.
- The `device_id` in session logs corresponds to the `account_session` label, allowing results from multiple devices or sessions to be compared directly.

---

## Disclaimer

These files specifically are at risk of becoming outdated if Instagram changes elements to its ever-updating UI, and may need to be modified for future use. They were originally used on Instagram Version 415.0.0.36.76 on a Google Pixel 5 using Genymotion.