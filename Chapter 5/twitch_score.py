#!/usr/bin/env python3
"""
Twitch Chat Toxicity Scorer
==============================
Scores Twitch chat CSV files (time, user_name, user_color, message)
with Detoxify and outputs per-streamer stats.

Usage:
    python twitch_score.py --input twitch_streams/ --output twitch_results/

Structure:
    twitch_streams/
        streamer_a/
            chat1.csv
            chat2.csv
        streamer_b/
            ...
    OR just:
    twitch_streams/
        chat1.csv
        chat2.csv
"""

import csv
import json
import sys
import re
import time as timer
import argparse
import statistics
from pathlib import Path
from collections import defaultdict, Counter

try:
    from detoxify import Detoxify
except ImportError:
    print("ERROR: pip install detoxify")
    sys.exit(1)

try:
    from scipy import stats as sp
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

ATTRS = ["toxicity", "severe_toxicity", "insult", "obscene", "identity_attack", "threat"]
LABELS = {"toxicity": "TOXICITY", "severe_toxicity": "SEVERE_TOXICITY",
          "insult": "INSULT", "obscene": "PROFANITY",
          "identity_attack": "IDENTITY_ATTACK", "threat": "THREAT"}

# ── Known Twitch emotes (global + common BTTV/FFZ/7TV) ──
# This is not exhaustive but covers the vast majority of emote-only messages.
# Add your own to the set or load from a file with --emote-file.
KNOWN_EMOTES = {
    # Twitch global
    "4Head", "ANELE", "ArgieB8", "ArsonNoSexy", "AsexualPride", "AsianGlow",
    "B)", "BCWarrior", "BOP", "BabyRage", "BatChest", "BegWan", "BibleThump",
    "BigBrother", "BigPhish", "BlargNaut", "BloodTrail", "BrainSlug", "BrokeBack",
    "BuddhaBar", "CaitlynS", "CarlSmile", "ChefFrank", "CoolCat", "CoolStoryBob",
    "CorgiDerp", "CurseLit", "DAESuppy", "DBstyle", "DansGame", "DarkMode",
    "DatSheffy", "DinoDance", "DogFace", "DoritosChip", "DxCat", "EarthDay",
    "EleGiggle", "EntropyWins", "ExtraLife", "FBBlock", "FBCatch", "FBChallenge",
    "FBPass", "FBPenalty", "FBRun", "FBSpiral", "FBtouchdown", "FailFish",
    "FallWinning", "FamilyMan", "FootBall", "FootGoal", "FootYellow", "FrankerZ",
    "FreakinStinkin", "FutureMan", "GayPride", "GenderFluidPride", "GivePLZ",
    "GlitchCat", "GlitchLit", "GlitchNRG", "GrammarKing", "GreenTeam",
    "GunRun", "HSCheers", "HSWP", "HSStageDive", "HahaCat", "HahaElf",
    "HahaGoose", "HahaHide", "HahaLean", "HahaNutcracker", "HahaPoint",
    "HahaPresent", "HahaShrugLeft", "HahaShrugMiddle", "HahaShrugRight",
    "HahaSnowhal", "HahaSleep", "HahaSweat", "HahaThink", "HahaThisisfine",
    "HahaTurtledove", "HappyJack", "HarleyWing", "HassaanChop", "HeyGuys",
    "HolidayCookie", "HolidayLog", "HolidayPresent", "HolidaySanta",
    "HolidayTree", "HotPokket", "HungryPaimon", "IconEarly", "IntersexPride",
    "InuyoFace", "ItsBoshyTime", "JKanStyle", "Jebaited", "JonCarnage",
    "KAPOW", "KPop", "KPOPcheer", "KPOPdance", "KPOPfan", "KPOPglow",
    "KPOPheart", "KPOPlove", "KPOPmerch", "KPOPselfie", "KPOPvictory",
    "Kappa", "KappaClaus", "KappaPride", "KappaRoss", "KappaWealth",
    "Keepo", "KevinTurtle", "Kippa", "KomodoHype", "Kreygasm",
    "LUL", "LaundryBasket", "Lechonk", "LesbianPride", "MVGame",
    "Mau5", "MaxLOL", "MercyWing1", "MercyWing2", "MikeHogu", "MingLee",
    "ModLove", "MorphinTime", "MrDestructoid", "NewRecord", "NiceTry",
    "NinjaGrumpy", "NomNom", "NonbinaryPride", "NotATK", "NotLikeThis",
    "OSFrog", "OhMyDog", "OneHand", "OpieOP", "OptimizePrime", "PJSalt",
    "PJSugar", "PMSTwin", "PRChase", "PanicVis", "PansexualPride",
    "PartyHat", "PartyTime", "PeoplesChamp", "PermaSmug", "PicoMause",
    "PinkMercy", "PipeHype", "PixelBob", "PizzaTime", "PogChamp",
    "Poooound", "PopCorn", "PoroSad", "PotFriend", "PowerUpL", "PowerUpR",
    "PraiseIt", "PrimeMe", "PunOko", "PunchTrees", "RaccAttack",
    "RalpherZ", "RedCoat", "RedTeam", "ResidentSleeper", "RitzMitz",
    "RlyTho", "RuleFive", "SSSsss", "SMOrc", "SabaPing", "SeemsGood",
    "SeriousSloth", "ShadyLulu", "ShazBotstix", "Shush", "SingsMic",
    "SingsNote", "SirMad", "SirPrise", "SirSad", "SirShield", "SirSword",
    "SirUwU", "SmoocherZ", "Squid1", "Squid2", "Squid3", "Squid4",
    "StinkyCheese", "StinkyGlitch", "StoneLightning", "StrawBeary",
    "SuperVinlin", "SwiftRage", "TBAngel", "TF2John", "TPFufun",
    "TPcrunchyroll", "TTours", "TakeNRG", "TearGlove", "TehePelo",
    "ThankEgg", "TheIlluminati", "TheRinger", "TheTarFu", "TheThing",
    "ThunBeast", "TinyFace", "TombRaid", "TooSpicy", "TransgenderPride",
    "TriHard", "TwitchConHYPE", "TwitchLit", "TwitchRPG", "TwitchSings",
    "TwitchUnity", "TwitchVotes", "UWot", "UnSane", "UncleNox",
    "VirtualHug", "VoHiYo", "VoteNay", "VoteYea", "WTRuck",
    "WholeWheat", "WutFace", "YouDontSay", "YouWHY", "bleedPurple",
    "cmonBruh", "copyThis", "duDudu", "imGlitch", "mcaT",
    "o_O", "panicBasket", "pastaThat", "riPepperonis", "twitchRaid",
    # BTTV / FFZ / 7TV popular
    "KEKW", "LULW", "OMEGALUL", "monkaS", "monkaW", "monkaHmm",
    "monkaGIGA", "PepeLaugh", "Pepega", "PepeHands", "FeelsBadMan",
    "FeelsGoodMan", "FeelsStrongMan", "FeelsBirthdayMan", "FeelsOkayMan",
    "FeelsWeirdMan", "FeelsDankMan", "PepoThink", "widepeepoHappy",
    "widepeepoSad", "peepoClap", "peepoGlad", "peepoRiot", "peepoLeave",
    "peepoArrive", "peepoGiggles", "peepoBlush", "peepoShy", "peepoWTF",
    "Sadge", "Madge", "Gladge", "Bedge", "Copege", "Susge", "Hapge",
    "catJAM", "catFight", "ratJAM", "HYPERS", "EZ", "Clap", "POGGERS",
    "PogU", "PogO", "WeirdChamp", "5Head", "3Head", "pepeMeltdown",
    "pepeJAM", "pepeD", "pepeDS", "pepePls", "TriKool", "RareParrot",
    "NODDERS", "NOPERS", "modCheck", "Chatting", "Clueless", "Aware",
    "forsenCD", "forsenE", "forsenPls", "xqcL", "xqcMald", "gachiHYPER",
    "gachiGASM", "gachiAPPROVE", "BOOBA", "AYAYA", "NaM", "KKona",
    "KKonaW", "D:", ":D", ":)", ":(", "<3", "O_o", "B)", ":O", ":P",
    ";)", "R)", ";P", ":Z", ":|", ":-|", ":-)", ":-(", ">(",
    "WAYTOODANK", "forsenBased", "basedCigar", "Stare", "MODS",
    "monkaTOS", "CiGrip", "COPIUM", "HOPIUM", "Prayge", "Okayge",
    "SillyChamp", "HandsUp", "PETTHE", "FeelsLagMan", "ICANT",
    "Wokege", "Nerdge", "Gigachad", "GIGACHAD", "Chad", "Based",
    "TrollDespair", "Despairge", "DIESOFCRINGE",
}

# Lowercase version for matching
KNOWN_EMOTES_LOWER = {e.lower() for e in KNOWN_EMOTES}

# ── Known Twitch bots ──
KNOWN_BOTS = {
    "nightbot", "streamelements", "fossabot", "moobot", "wizebot",
    "streamlabs", "stay_hydrated_bot", "soundalerts", "pretzelrocks",
    "commanderroot", "ankhbot", "deepbot", "phantombot", "botisimo",
    "coebot", "vivbot", "streamholics", "hnlbot", "ohbot",
    "twitchprimereminder", "restreambot", "own3d", "lolrankbot",
    "supibot", "okayeg", "apulux", "logviewer", "streamkit",
    "pokemoncommunitygame", "acebot", "creatisbot", "songlistbot",
    "titsbot", "buttsbot", "mikuia", "scottybot", "xanbot",
}


def is_emote_only(text: str) -> bool:
    """Check if a message consists entirely of known emotes (and whitespace/punctuation)."""
    words = text.split()
    if not words:
        return False
    non_emote_words = 0
    for word in words:
        # Strip common suffixes/repeats
        clean = word.strip(".,!?:;")
        if clean.lower() in KNOWN_EMOTES_LOWER or clean in KNOWN_EMOTES:
            continue
        # Check if it's a number (emote spam like "7777")
        if clean.isdigit():
            continue
        # Check if it's a repeated single char ("AAAA", "???")
        if len(set(clean.lower())) <= 1 and len(clean) > 1:
            continue
        non_emote_words += 1

    return non_emote_words == 0


def is_bot(username: str) -> bool:
    """Check if a username is a known bot."""
    return username.lower().strip() in KNOWN_BOTS


def load_custom_emotes(path: str) -> set:
    """Load additional emotes from a text file (one per line)."""
    emotes = set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            e = line.strip()
            if e and not e.startswith("#"):
                emotes.add(e)
                emotes.add(e.lower())
    return emotes


def load_twitch_csvs(folder):
    """Load all CSVs in a folder, handle various formats."""
    msgs = []
    for f in sorted(Path(folder).glob("*.csv")):
        with open(f, "r", encoding="utf-8", errors="replace") as fh:
            # Sniff delimiter
            sample = fh.read(2048)
            fh.seek(0)

            # Detect header
            first_line = sample.split("\n")[0].lower()
            if "message" not in first_line and "msg" not in first_line:
                # No header — assume: time, user_name, user_color, message
                reader = csv.reader(fh)
                for row in reader:
                    if len(row) >= 4:
                        msgs.append({
                            "time": row[0].strip(),
                            "username": row[1].strip(),
                            "user_color": row[2].strip(),
                            "message": row[3].strip(),
                            "file": f.name,
                        })
                    elif len(row) >= 2:
                        msgs.append({
                            "time": row[0].strip(),
                            "username": "",
                            "user_color": "",
                            "message": row[-1].strip(),
                            "file": f.name,
                        })
            else:
                reader = csv.DictReader(fh)
                for row in reader:
                    # Flexible column matching
                    msg_text = (row.get("message") or row.get("msg") or
                                row.get("text") or row.get("content") or "").strip()
                    username = (row.get("user_name") or row.get("username") or
                                row.get("user") or row.get("author") or "").strip()
                    ts = (row.get("time") or row.get("timestamp") or
                          row.get("created_at") or row.get("date") or "").strip()
                    color = (row.get("user_color") or row.get("color") or "").strip()

                    if msg_text:
                        msgs.append({
                            "time": ts,
                            "username": username,
                            "user_color": color,
                            "message": msg_text,
                            "file": f.name,
                        })

        print(f"    {f.name}: {sum(1 for m in msgs if m['file'] == f.name):,} messages")

    return msgs


def score_messages(msgs, model, batch_size=128):
    """Score text messages, filtering out emote-only, bots, and commands."""
    scoreable = []
    n_emote_only = 0
    n_bot = 0
    n_command = 0
    n_short = 0

    for m in msgs:
        text = m["message"]
        username = m.get("username", "")

        if len(text) < 3:
            n_short += 1
            continue
        if text.startswith("!") or text.startswith("/"):
            n_command += 1
            continue
        if is_bot(username):
            n_bot += 1
            continue
        if is_emote_only(text):
            n_emote_only += 1
            continue
        scoreable.append(m)

    print(f"    Filtered: {n_emote_only:,} emote-only, {n_bot:,} bot, "
          f"{n_command:,} commands, {n_short:,} too short")
    print(f"    Remaining: {len(scoreable):,} to score")

    if not scoreable:
        return []

    print(f"    Scoring {len(scoreable):,} messages...")
    results = []
    start = timer.time()

    for i in range(0, len(scoreable), batch_size):
        batch = scoreable[i:i + batch_size]
        texts = [m["message"] for m in batch]
        scores = model.predict(texts)

        for j, msg in enumerate(batch):
            row = {
                "time": msg["time"],
                "username": msg["username"],
                "message": msg["message"],
                "file": msg["file"],
            }
            for attr in ATTRS:
                row[LABELS[attr]] = scores[attr][j]
            results.append(row)

        done = min(i + batch_size, len(scoreable))
        if done % (batch_size * 20) == 0 or done >= len(scoreable):
            elapsed = timer.time() - start
            rate = done / elapsed if elapsed > 0 else 0
            print(f"      {done:,}/{len(scoreable):,} ({rate:.0f}/sec)")

    print(f"    Done: {len(results):,} scored in {timer.time()-start:.1f}s")
    return results


def analyze(name, msgs, scored):
    """Compute stats for one streamer."""
    n_users = len(set(m["username"] for m in msgs if m["username"]))

    result = {
        "streamer": name,
        "total_messages": len(msgs),
        "scored_messages": len(scored),
        "unique_users": n_users,
    }

    if not scored:
        return result

    # Per-attribute stats
    for label in LABELS.values():
        vals = [r[label] for r in scored]
        result[label] = {
            "mean": round(statistics.mean(vals), 4),
            "median": round(statistics.median(vals), 4),
            "pct_above_03": round(sum(1 for v in vals if v > 0.3) / len(vals) * 100, 2),
            "pct_above_05": round(sum(1 for v in vals if v > 0.5) / len(vals) * 100, 2),
            "pct_above_07": round(sum(1 for v in vals if v > 0.7) / len(vals) * 100, 2),
        }

    # Concentration
    user_counts = Counter(r["username"] for r in scored if r["username"])
    counts = sorted(user_counts.values(), reverse=True)
    if counts:
        n = len(counts)
        top1 = max(1, n // 100)
        top10 = max(1, n // 10)
        total = sum(counts)
        result["concentration"] = {
            "top_1pct_msg_share": round(sum(counts[:top1]) / total * 100, 1),
            "top_10pct_msg_share": round(sum(counts[:top10]) / total * 100, 1),
            "median_msgs_per_user": statistics.median(counts),
        }

    # Per-user toxicity
    user_tox = defaultdict(list)
    for r in scored:
        if r["username"]:
            user_tox[r["username"]].append(r["TOXICITY"])

    # Top toxic users
    user_means = [(u, statistics.mean(v), len(v)) for u, v in user_tox.items() if len(v) >= 10]
    user_means.sort(key=lambda x: x[1], reverse=True)
    result["top_toxic_users"] = [
        {"username": u, "mean_toxicity": round(m, 4), "n_msgs": n}
        for u, m, n in user_means[:15]
    ]

    # Contagion
    sorted_scored = sorted(scored, key=lambda r: r["time"])
    tox_vals = [r["TOXICITY"] for r in sorted_scored]
    if len(tox_vals) > 100:
        after_toxic = []
        after_clean = []
        window = 5
        for i in range(len(tox_vals) - window):
            following = statistics.mean(tox_vals[i+1:i+1+window])
            if tox_vals[i] >= 0.5:
                after_toxic.append(following)
            elif tox_vals[i] < 0.1:
                after_clean.append(following)

        if after_toxic and after_clean:
            result["contagion"] = {
                "n_toxic_triggers": len(after_toxic),
                "n_clean_triggers": len(after_clean),
                "mean_after_toxic": round(statistics.mean(after_toxic), 4),
                "mean_after_clean": round(statistics.mean(after_clean), 4),
                "ratio": round(statistics.mean(after_toxic) / max(statistics.mean(after_clean), 0.0001), 2),
            }
            if HAS_SCIPY and len(after_toxic) >= 5 and len(after_clean) >= 5:
                stat, pval = sp.mannwhitneyu(after_toxic, after_clean, alternative='greater')
                result["contagion"]["mann_whitney_p"] = round(pval, 6)
                result["contagion"]["significant"] = pval < 0.05

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", "-i", required=True, help="twitch_streams/ directory")
    parser.add_argument("--output", "-o", default="twitch_results", help="Output directory")
    parser.add_argument("--model", default="unbiased", choices=["original", "unbiased", "original-small", "unbiased-small"])
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--emote-file", default=None,
                        help="Text file with additional emote names (one per line)")
    parser.add_argument("--bot-file", default=None,
                        help="Text file with additional bot usernames (one per line)")
    args = parser.parse_args()

    # Load custom emotes/bots if provided
    if args.emote_file:
        custom = load_custom_emotes(args.emote_file)
        KNOWN_EMOTES.update(custom)
        KNOWN_EMOTES_LOWER.update(e.lower() for e in custom)
        print(f"  Loaded {len(custom)} custom emotes from {args.emote_file}")

    if args.bot_file:
        with open(args.bot_file, "r") as f:
            for line in f:
                b = line.strip().lower()
                if b and not b.startswith("#"):
                    KNOWN_BOTS.add(b)
        print(f"  Loaded custom bots from {args.bot_file}")

    root = Path(args.input)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    # Discover structure: subfolders or flat
    subdirs = [d for d in sorted(root.iterdir()) if d.is_dir() and list(d.glob("*.csv"))]
    if subdirs:
        streamers = {d.name: d for d in subdirs}
    elif list(root.glob("*.csv")):
        streamers = {root.name: root}
    else:
        print("No CSV files found")
        sys.exit(1)

    print("=" * 60)
    print(f"  TWITCH CHAT TOXICITY SCORER")
    print(f"  Model: Detoxify ({args.model})")
    print(f"  Streamers: {', '.join(streamers.keys())}")
    print("=" * 60)

    print(f"\n  Loading model...")
    model = Detoxify(args.model)
    print(f"  Ready!")

    all_results = {}

    for name, folder in streamers.items():
        print(f"\n{'='*55}")
        print(f"  {name}")
        print(f"{'='*55}")

        print(f"  Loading CSVs...")
        msgs = load_twitch_csvs(folder)
        print(f"  {len(msgs):,} total messages")

        if not msgs:
            continue

        scored = score_messages(msgs, model, batch_size=args.batch_size)
        result = analyze(name, msgs, scored)
        all_results[name] = result

        # Export scored CSV
        sdir = out / name
        sdir.mkdir(parents=True, exist_ok=True)

        if scored:
            csv_path = sdir / "scored_messages.csv"
            keys = list(scored[0].keys())
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=keys)
                w.writeheader()
                for r in scored:
                    w.writerow(r)
            print(f"  → {csv_path}")

        # Export analysis
        json_path = sdir / "analysis.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"  → {json_path}")

        # Print summary
        if "TOXICITY" in result:
            t = result["TOXICITY"]
            print(f"\n  TOXICITY:        mean={t['mean']:.4f}  median={t['median']:.4f}  >0.5={t['pct_above_05']:.1f}%  >0.7={t['pct_above_07']:.1f}%")
        for attr in ["INSULT", "PROFANITY", "IDENTITY_ATTACK", "THREAT"]:
            if attr in result:
                a = result[attr]
                print(f"  {attr:18s} mean={a['mean']:.4f}  >0.5={a['pct_above_05']:.1f}%")
        if "contagion" in result:
            c = result["contagion"]
            print(f"  Contagion: {c['ratio']:.2f}x  "
                  f"{'significant' if c.get('significant') else 'not significant'}")

    # Cross-streamer comparison
    if len(all_results) > 1:
        print(f"\n{'='*60}")
        print(f"  CROSS-STREAMER COMPARISON")
        print(f"{'='*60}")
        print(f"\n  {'Streamer':15s} {'Msgs':>8s} {'Users':>7s} {'Tox':>7s} {'Insult':>7s} {'Prof':>7s} {'IdAtk':>7s} {'Threat':>7s} {'>0.5%':>6s}")
        print(f"  {'-'*75}")
        for name in sorted(all_results.keys()):
            r = all_results[name]
            tox = r.get("TOXICITY", {})
            ins = r.get("INSULT", {})
            pro = r.get("PROFANITY", {})
            ida = r.get("IDENTITY_ATTACK", {})
            thr = r.get("THREAT", {})
            print(f"  {name:15s} {r['scored_messages']:8,d} {r['unique_users']:7,d} "
                  f"{tox.get('mean',0):7.4f} {ins.get('mean',0):7.4f} "
                  f"{pro.get('mean',0):7.4f} {ida.get('mean',0):7.4f} "
                  f"{thr.get('mean',0):7.4f} {tox.get('pct_above_05',0):5.1f}%")

    combined_path = out / "twitch_combined.json"
    with open(combined_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\n  → {combined_path}")

    print(f"\n{'='*60}")
    print(f"  Done!")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()