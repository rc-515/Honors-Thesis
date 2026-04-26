import os
import json
import subprocess
import argparse

def main():
    # Set up argument parsing to take the account name from the command line
    parser = argparse.ArgumentParser(description="Download reels for a specific account.")
    parser.add_argument("account", help="The name of the account to process")
    args = parser.parse_args()

    account = args.account

    # Format the directories dynamically using the provided account name
    LOGS_DIR = f"logs/{account}_new"
    OUTPUT_DIR = f"videos/{account}_new"

    # Safety check: ensure the logs directory exists before proceeding
    if not os.path.exists(LOGS_DIR):
        print(f"Error: The directory '{LOGS_DIR}' does not exist.")
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for filename in os.listdir(LOGS_DIR):
        if filename.endswith("_session.json"):
            filepath = os.path.join(LOGS_DIR, filename)

            print(f"\nProcessing file: {filename}")

            with open(filepath, "r") as f:
                data = json.load(f)

            for item in data:
                url = item.get("reel_url")

                if not url or url == "NOT_FOUND":
                    continue

                # Skip non-reel URLs (photo posts, stories, etc.)
                if "/reel/" not in url:
                    print(f"Skipping non-reel URL: {url}")
                    continue

                video_id = url.split("?")[0].rstrip("/").split("/")[-1]

                output_path = os.path.join(OUTPUT_DIR, f"{video_id}.mp4")

                if os.path.exists(output_path):
                    print(f"Already downloaded: {video_id}.mp4 — skipping")
                    continue

                print(f"Downloading: {url} -> {video_id}.mp4")

                try:
                    subprocess.run([
                        "yt-dlp",
                        "--cookies", "cookies.txt",
                        "--sleep-interval", "3",
                        "--max-sleep-interval", "6",
                        "-o", output_path,
                        url
                    ], check=True)
                except subprocess.CalledProcessError as e:
                    print(f"Download failed for {video_id}: {e}")

if __name__ == "__main__":
    main()