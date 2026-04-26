from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from time import sleep
import json
import os
import argparse
from datetime import datetime

# ========== CONFIG ==========
REELS_TO_CAPTURE = 30
WATCH_TIME = 8  # seconds per reel

# Globals that will be set via command line
SESSION_ID = None
UDID = None
width = height = start_x = start_y = end_y = 0
# ============================

# ---------- HELPERS ----------

def create_driver(device_udid):
    options = UiAutomator2Options()
    options.platform_name = "Android"
    options.automation_name = "UiAutomator2"
    options.device_name = "AndroidDevice"
    options.udid = device_udid
    options.no_reset = True
    options.new_command_timeout = 300

    d = webdriver.Remote("http://127.0.0.1:4723", options=options)
    print("Attached to device.")
    return d


def is_ad(driver):
    try:
        # Strong signal: Learn More button
        learn = driver.find_elements(
            AppiumBy.ANDROID_UIAUTOMATOR,
            'new UiSelector().text("Ad")'
        )

        if learn:
            return True

        # Other CTA buttons common in ads
        cta = driver.find_elements(
            AppiumBy.ANDROID_UIAUTOMATOR,
            'new UiSelector().textMatches(".*(Install|Shop|Download).*")'
        )

        if cta:
            return True

        # Fallback: look for Sponsored (still useful sometimes)
        sponsored = driver.find_elements(
            AppiumBy.ANDROID_UIAUTOMATOR,
            'new UiSelector().textContains("Sponsored")'
        )

        if sponsored:
            return True

        return False

    except:
        return False


def safe_find(driver, strategy, value):
    elements = driver.find_elements(strategy, value)
    return elements[0] if elements else None


def swipe_up(driver):
    # Uses the global coordinates calculated in the main block
    driver.swipe(start_x, start_y, start_x, end_y, 800)


# ---------- MAIN EXECUTION ----------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Appium Instagram Reels Capture Bot")
    parser.add_argument("account", help="The account name")
    parser.add_argument("session_number", help="The session number (e.g., 1, 2, 3)")
    parser.add_argument("--udid", required=True, help="The device UDID (e.g., 192.168.1.100:5555)")
    args = parser.parse_args()

    # Assign to globals
    SESSION_ID = f"{args.account}_{args.session_number}"
    UDID = args.udid

    print(f"Watching {REELS_TO_CAPTURE} reels for session {SESSION_ID} on device {UDID}")

    # Setup
    os.makedirs("logs", exist_ok=True)
    driver = create_driver(UDID)

    # Screen dimensions
    size = driver.get_window_size()
    width = size["width"]
    height = size["height"]

    start_x = width // 2
    start_y = int(height * 0.8)
    end_y = int(height * 0.2)

    records = []
    captured = 0
    seen = 0  # total screens seen (including ads)

    # Main Loop
    while captured < REELS_TO_CAPTURE:
        print(f"\nLooking at screen {seen+1}")

        sleep(WATCH_TIME)

        # Skip ads completely
        if is_ad(driver):
            print("Ad detected — skipping")

            try:
                swipe_up(driver)
            except:
                pass

            sleep(2)
            seen += 1
            continue

        print(f"Processing reel {captured+1}")

        timestamp = datetime.utcnow().isoformat()

        screenshot_path = f"logs/{SESSION_ID}_reel_{captured+1}.png"
        sleep(2)  # let UI settle
        success = False

        for attempt in range(3):
            try:
                sleep(2)
                driver.save_screenshot(screenshot_path)
                success = True
                break
            except Exception as e:
                print(f"Screenshot attempt {attempt+1} failed:", e)
                sleep(2)

        if not success:
            print("Skipping reel due to screenshot failure")
            swipe_up(driver)
            sleep(3)
            continue

        reel_link = "NOT_FOUND"

        try:
            share_button = safe_find(
                driver,
                AppiumBy.ANDROID_UIAUTOMATOR,
                'new UiSelector().descriptionContains("Share")'
            )

            if share_button:
                share_button.click()
                sleep(2)

                copy_link = safe_find(
                    driver,
                    AppiumBy.ANDROID_UIAUTOMATOR,
                    'new UiSelector().textContains("Copy")'
                )

                if copy_link:
                    copy_link.click()
                    sleep(1)

                    reel_link = driver.get_clipboard_text()
                    print("Copied link:", reel_link)

                else:
                    print("No Copy button — skipping link")

                driver.back()
                sleep(1)

            else:
                print("No Share button — skipping link")

        except Exception as e:
            print("Error during processing:", e)
            try:
                driver.back()
            except:
                pass

        record = {
            "SESSION_ID": SESSION_ID,
            "reel_index": captured + 1,
            "timestamp_utc": timestamp,
            "reel_url": reel_link,
            "screenshot_path": screenshot_path
        }

        records.append(record)

        captured += 1
        seen += 1

        # Always swipe
        try:
            swipe_up(driver)
        except:
            swipe_up(driver)

        sleep(3)

    # ---------- CLEANUP ----------

    driver.quit()

    log_path = f"logs/{SESSION_ID}_session.json"
    with open(log_path, "w") as f:
        json.dump(records, f, indent=4)

    print(f"\nDone. Saved logs to {log_path}")