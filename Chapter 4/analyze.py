import json
import os
import cv2
import base64
import time
import requests
import argparse
from urllib.parse import urlparse
from faster_whisper import WhisperModel

# -----------------------------
# CONFIG
# -----------------------------

GEMINI_MODEL = "gemini-2.5-flash"
NUM_FRAMES = 5
MAX_RETRIES = 5

# -----------------------------
# EXPECTED OUTPUT SCHEMA
# -----------------------------
 
EXPECTED_FIELDS = {
    "description": str,
    "gender_target": ["men", "women", "neutral"],
    "political_content": [0, 1],
    "political_leaning": ["left", "right", "center", "none"],
    "traditional_gender_roles": [0, 1],
    "military_patriotic_law_enforcement": [0, 1],
    "religion": [0, 1],
    "edgy_humor": [0, 1],
    "violence": [0, 1],
    "guns_weapons": [0, 1],
    "sexual_suggestive": [0, 1],
    "rage_bait_outrage": [0, 1],
    "conspiratorial": [0, 1],
    "pseudoscientific": [0, 1],
    "extreme": [0, 1],
    "radical": [0, 1],
    "discriminatory": [0, 1],
    "incel-related": [0, 1],
    "anti_woke_anti_progressive": [0, 1],
    "masculinity_femininity_focus": ["masculinity", "femininity", "none"],
    "topic": ["politics", "fitness", "comedy", "news", "lifestyle", "finance",
              "sports", "education", "music", "food", "tech", "religion", "other"],
    "notes": str,
}
 
 
def validate_analysis(analysis):
    """Returns list of problems. Empty = valid."""
    if not isinstance(analysis, dict):
        return ["not a dict"]
    if "error" in analysis:
        return [f"error: {analysis['error']}"]
 
    problems = []
    for field, valid in EXPECTED_FIELDS.items():
        if field not in analysis:
            problems.append(f"missing: {field}")
            continue
        value = analysis[field]
        if valid == str:
            if not isinstance(value, str):
                problems.append(f"{field}: expected string, got {repr(value)}")
            elif field != "notes" and not value.strip():
                problems.append(f"{field}: expected non-empty string")
        elif isinstance(valid, list):
            if value not in valid:
                problems.append(f"{field}: {repr(value)} not in {valid}")
    return problems
 
 
# -----------------------------
# WHISPER SETUP
# -----------------------------
 
whisper_model = WhisperModel(
    "base",
    device="cpu",
    compute_type="int8"
)
 
 
def transcribe_audio(video_path):
    try:
        segments, info = whisper_model.transcribe(video_path, beam_size=5)
        full_text = ""
        for segment in segments:
            full_text += segment.text + " "
        return full_text.strip()
    except Exception as e:
        print(f"  Transcription failed (no audio?): {e}")
        return ""
 
 
# -----------------------------
# FRAME EXTRACTION
# -----------------------------
 
def extract_frames(video_path, num_frames=5):
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
 
    if total_frames <= 0:
        cap.release()
        return []
 
    start = int(total_frames * 0.1)
    end = int(total_frames * 0.9)
 
    if end <= start:
        start = 0
        end = total_frames - 1
 
    indices = [int(start + i * (end - start) / (num_frames - 1)) for i in range(num_frames)]
 
    frames_b64 = []
 
    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret:
            continue
 
        h, w = frame.shape[:2]
        max_dim = 768
        if max(h, w) > max_dim:
            scale = max_dim / max(h, w)
            frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
 
        _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        b64 = base64.b64encode(buffer).decode("utf-8")
        frames_b64.append(b64)
 
    cap.release()
    return frames_b64
 
 
# -----------------------------
# GEMINI API CALL
# -----------------------------
 
def send_to_gemini(frames_b64, caption, transcript, api_key):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={api_key}"
 
    parts = []
 
    for b64 in frames_b64:
        parts.append({
            "inline_data": {
                "mime_type": "image/jpeg",
                "data": b64
            }
        })
 
    text_block = f"""You are a content analyst for an academic research study examining what Instagram's algorithm recommends to different users. Analyze this Instagram Reel using the keyframes, caption, and transcript provided.
 
INSTAGRAM CAPTION:
{caption}
 
SPOKEN TRANSCRIPT:
{transcript}
 
Respond with ONLY a valid JSON object using exactly these fields:
 
{{
  "description": "One sentence describing what the reel shows",
  "gender_target": "men" or "women" or "neutral",
  "political_content": 0 or 1,
  "political_leaning": "left" or "right" or "center" or "none",
  "traditional_gender_roles": 0 or 1,
  "military_patriotic_law_enforcement": 0 or 1,
  "religion": 0 or 1,
  "edgy_humor": 0 or 1,
  "violence": 0 or 1,
  "guns_weapons": 0 or 1,
  "sexual_suggestive": 0 or 1,
  "rage_bait_outrage": 0 or 1,
  "conspiratorial": 0 or 1,
  "pseudoscientific": 0 or 1,
  "extreme": 0 or 1,
  "radical": 0 or 1,
  "discriminatory": 0 or 1,
  "incel-related": 0 or 1,
  "anti_woke_anti_progressive": 0 or 1,
  "masculinity_femininity_focus": "masculinity" or "femininity" or "none",
  "topic": "politics" or "fitness" or "comedy" or "news" or "lifestyle" or "finance" or "sports" or "education" or "music" or "food" or "tech" or "religion" or "other",
  "notes": "Any additional context relevant to political leaning or gendered targeting"
}}
 
Rules:
- political_leaning should reflect the overall slant of the content, not just whether politics is mentioned
- traditional_gender_roles means content reinforcing conventional expectations of men or women
- anti_woke_anti_progressive means content mocking or criticizing progressive social movements
- rage_bait_outrage means content designed to provoke anger or outrage for engagement
- conspiratorial means propagating unverified or false conspiracy theories
- pseudoscientific means presenting false or unsupported claims under the guise of science
- extreme means promoting violent ideologies or social disruption
- radical means encouraging viewers to adopt extreme ideologies
- discriminatory means expressing hate for outside groups
- incel-related includes anything anti-feminist and anti-woman
- Be objective. Code what is present in the content, not your opinion of it.
"""
 
    parts.append({"text": text_block})
 
    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": 4096,
            "response_mime_type": "application/json"
        }
    }
 
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, headers=headers, json=payload)
 
    if response.status_code != 200:
        print(f"  Gemini API error {response.status_code}: {response.text[:300]}")
        return {"error": response.text}
 
    result = response.json()
 
    try:
        raw_text = result["candidates"][0]["content"]["parts"][0]["text"]
        cleaned = raw_text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(cleaned)
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        print(f"  Parse error: {e}")
        return {"error": "parse_failed"}
 
 
# -----------------------------
# ANALYZE WITH VALIDATION + RETRY
# -----------------------------
 
def analyze_reel(frames, caption, transcript, api_key):
    """Send to Gemini and retry until valid or max retries hit."""
    for attempt in range(1, MAX_RETRIES + 1):
        analysis = send_to_gemini(frames, caption, transcript, api_key)
        problems = validate_analysis(analysis)
 
        if not problems:
            return analysis
 
        print(f"  Attempt {attempt}/{MAX_RETRIES} invalid: {problems[0]}")
        time.sleep(1)
 
    print(f"  FAILED after {MAX_RETRIES} attempts")
    return analysis  # return last attempt even if bad
 
 
# -----------------------------
# MAIN
# -----------------------------
 
def process_all(account, api_key):
    # Dynamic directories based on the command line input
    LOGS_FOLDER = f"logs/{account}"
    DOWNLOAD_FOLDER = f"videos/{account}"
    OUTPUT_JSON = f"processed_{account}.json"

    # Safety checks
    if not os.path.exists(LOGS_FOLDER):
        print(f"Error: The log directory '{LOGS_FOLDER}' does not exist.")
        return
    
    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

    session_files = sorted([
        f for f in os.listdir(LOGS_FOLDER)
        if f.endswith("_session.json")
    ])
 
    if not session_files:
        print(f"No session files found in {LOGS_FOLDER}")
        return
 
    print(f"Found {len(session_files)} session file(s): {session_files}\n")
 
    # Resume support
    already_done = set()
    all_results = []
 
    if os.path.exists(OUTPUT_JSON):
        with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
            all_results = json.load(f)
        # Only count entries with valid analysis as done
        for entry in all_results:
            if not validate_analysis(entry.get("gemini_analysis")):
                already_done.add(entry["shortcode"])
        print(f"Resuming — {len(already_done)} valid entries already done\n")
 
    for session_file in session_files:
        session_path = os.path.join(LOGS_FOLDER, session_file)
        session_name = session_file.replace("_session.json", "")
 
        print(f"{'='*50}")
        print(f"SESSION: {session_file}")
        print(f"{'='*50}")
 
        with open(session_path, "r", encoding="utf-8") as f:
            reels = json.load(f)
 
        for reel in reels:
            reel_url = reel.get("reel_url", "")
            device_id = reel.get("device_id", session_name)
            reel_index = reel.get("reel_index", 0)
 
            if reel.get("skip", False):
                continue
 
            if not reel_url or reel_url == "NOT_FOUND":
                continue
 
            shortcode = urlparse(reel_url).path.strip("/").split("/")[-1]
 
            if shortcode in already_done:
                print(f"\n  Already done: {shortcode}")
                continue
 
            # Check if this shortcode has a bad entry we should re-process
            existing_idx = None
            for idx, existing in enumerate(all_results):
                if existing.get("shortcode") == shortcode:
                    existing_idx = idx
                    break
 
            print(f"\nProcessing {shortcode} (session={session_name}, reel {reel_index})")
 
            # Find video
            video_file = None
            caption_file = None
 
            for file in os.listdir(DOWNLOAD_FOLDER):
                if file.endswith(".mp4") and shortcode in file:
                    video_file = os.path.join(DOWNLOAD_FOLDER, file)
                if file.endswith(".txt") and shortcode in file:
                    caption_file = os.path.join(DOWNLOAD_FOLDER, file)
 
            if not video_file:
                print(f"  Video not found — skipping")
                continue
 
            # Caption
            instagram_caption = ""
            if caption_file and os.path.exists(caption_file):
                with open(caption_file, "r", encoding="utf-8") as f:
                    instagram_caption = f.read().strip()
 
            # Transcribe
            print("  Transcribing...")
            spoken_transcript = transcribe_audio(video_file)
 
            # Extract frames
            print(f"  Extracting {NUM_FRAMES} frames...")
            frames = extract_frames(video_file, NUM_FRAMES)
            print(f"  Got {len(frames)} frames")
 
            # Analyze with retry
            print("  Analyzing...")
            gemini_analysis = analyze_reel(frames, instagram_caption, spoken_transcript, api_key)
 
            valid = not validate_analysis(gemini_analysis)
            print(f"  Valid: {valid}")
 
            result = {
                "session_file": session_file,
                "device_id": device_id,
                "reel_index": reel_index,
                "shortcode": shortcode,
                "reel_url": reel_url,
                "instagram_caption": instagram_caption,
                "spoken_transcript": spoken_transcript,
                "num_frames_sent": len(frames),
                "gemini_analysis": gemini_analysis
            }
 
            # Update existing or append new
            if existing_idx is not None:
                all_results[existing_idx] = result
            else:
                all_results.append(result)
 
            # Save after every reel
            with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
                json.dump(all_results, f, indent=4)
 
    # Final summary
    total = len(all_results)
    valid_count = sum(1 for r in all_results if not validate_analysis(r.get("gemini_analysis")))
    invalid_count = total - valid_count
 
    print(f"\n{'='*50}")
    print(f"Done. {total} reels total, {valid_count} valid, {invalid_count} invalid.")
    print(f"Saved to {OUTPUT_JSON}")
 
 
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze reels for a specific account.")
    parser.add_argument("account", help="The name of the account to process")
    parser.add_argument("--api-key", required=True, help="Your Gemini API key")
    args = parser.parse_args()
    
    process_all(args.account, args.api_key)