from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from time import sleep
import json
import os
import argparse
from datetime import datetime

# ========== CONFIG ==========
REELS_TO_ENGAGE = 50
WATCH_TIME = 10  # seconds per reel

# Globals that will be set via command line
SESSION_ID = None
UDID = None
driver = None
width = height = start_x = start_y = end_y = 0
# ============================

# ---------- HELPERS ----------

def create_driver():
    options = UiAutomator2Options()
    options.platform_name = "Android"
    options.automation_name = "UiAutomator2"
    options.device_name = "AndroidDevice"
    options.udid = UDID
    options.no_reset = True
    options.new_command_timeout = 300
    d = webdriver.Remote("http://127.0.0.1:4723", options=options)
    print("Attached to device.")
    return d


def reconnect():
    """Kill old session and create a new one."""
    global driver
    print("  Reconnecting to device...")
    try:
        driver.quit()
    except:
        pass
    sleep(5)
    driver = create_driver()
    sleep(3)
    print("  Reconnected.")


def safe_action(action_fn, action_name, max_retries=2):
    """Run an action with crash recovery."""
    for attempt in range(max_retries):
        try:
            return action_fn()
        except Exception as e:
            if "instrumentation process is not running" in str(e):
                print(f"  {action_name}: UiAutomator2 crashed — reconnecting...")
                reconnect()
            else:
                print(f"  {action_name} failed: {e}")
                return False
    return False


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


def safe_find(d, strategy, value):
    elements = d.find_elements(strategy, value)
    return elements[0] if elements else None


def swipe_up():
    driver.swipe(start_x, start_y, start_x, end_y, 800)


def like_reel():
    like_button = safe_find(
        driver,
        AppiumBy.ANDROID_UIAUTOMATOR,
        'new UiSelector().descriptionContains("Like")'
    )
    if like_button:
        like_button.click()
        sleep(1)
        return True
    print("  Like button not found")
    return False


def save_reel():
    save_button = safe_find(
        driver,
        AppiumBy.ANDROID_UIAUTOMATOR,
        'new UiSelector().descriptionContains("Save")'
    )
    if save_button:
        save_button.click()
        sleep(1)
        return True

    bookmark = safe_find(
        driver,
        AppiumBy.ANDROID_UIAUTOMATOR,
        'new UiSelector().descriptionContains("Bookmark")'
    )
    if bookmark:
        bookmark.click()
        sleep(1)
        return True

    print("  Save button not found")
    return False


def tap_top_quarter():
    driver.tap([(width // 2, height // 4)])
    return True


# ---------- MAIN EXECUTION ----------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Appium Instagram Engagement Bot")
    parser.add_argument("account", help="The account name")
    parser.add_argument("session_number", help="The session number (e.g., 1, 2, 3)")
    parser.add_argument("--udid", required=True, help="The device UDID from adb devices, in format XXX.XXX.XX.XXX:XXXX")
    args = parser.parse_args()

    # Assign to globals
    SESSION_ID = f"{args.account}_{args.session_number}"
    UDID = args.udid

    print(f"Engaging with {REELS_TO_ENGAGE} reels (like + save) on device {UDID}")

    # Setup
    os.makedirs("logs", exist_ok=True)
    driver = create_driver()

    # Screen dimensions
    size = driver.get_window_size()
    width = size["width"]
    height = size["height"]

    start_x = width // 2
    start_y = int(height * 0.8)
    end_y = int(height * 0.2)

    records = []
    engaged = 0
    seen = 0

    # Main Loop
    while engaged < REELS_TO_ENGAGE:
        print(f"\nLooking at screen {seen+1}")

        sleep(WATCH_TIME)

        # Skip ads
        ad = safe_action(lambda: is_ad(driver), "Ad check")
        if ad:
            print("Ad detected — skipping")
            safe_action(swipe_up, "Swipe")
            sleep(2)
            seen += 1
            continue

        print(f"Engaging with reel {engaged+1}")

        # Like it
        liked = safe_action(like_reel, "Like")
        print(f"  Liked: {liked}")

        # Save it
        saved = safe_action(save_reel, "Save")
        print(f"  Saved: {saved}")

        # Tap top quarter to dismiss overlay, then wait
        sleep(1)
        safe_action(tap_top_quarter, "Tap top")
        sleep(2)

        timestamp = datetime.utcnow().isoformat()

        record = {
            "SESSION_ID": SESSION_ID,
            "reel_index": engaged + 1,
            "timestamp_utc": timestamp,
            "liked": bool(liked),
            "saved": bool(saved)
        }

        records.append(record)

        engaged += 1
        seen += 1

        # Swipe to next
        safe_action(swipe_up, "Swipe")
        sleep(3)

    # Cleanup
    driver.quit()

    log_path = f"logs/{SESSION_ID}_engagement_session.json"
    with open(log_path, "w") as f:
        json.dump(records, f, indent=4)

    print(f"\nDone. Engaged with {engaged} reels ({seen} total seen including ads).")
    print(f"Saved logs to: {log_path}")