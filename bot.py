import feedparser
import requests
import json
import time
import os
from pathlib import Path
from urllib.parse import urlparse, urlunparse

# ===== 設定 =====
RSS_URL = "https://androiddagashi.github.io/feed.xml"
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")  # GitHub Actions対応

STATE_FILE = Path("state.json")
SEND_INTERVAL = 0.7
MAX_LINKS = 1000
CHECK_ENTRIES = 2


# ===== URL正規化 =====
def normalize_url(url: str):
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


# ===== 永続化 =====
def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"sent_ids": []}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ===== Discord送信 =====
def send_discord(title: str, link: str, summary: str):
    payload = {
        "embeds": [
            {
                "title": title,
                "url": link,
                "description": summary[:200],  # 長すぎ防止
                "footer": {"text": "AndroidDagashi Bot"},
                "color": 0x3DDC84,
            }
        ]
    }

    while True:
        res = requests.post(WEBHOOK_URL, json=payload, timeout=10)

        if res.status_code == 429:
            retry = res.json().get("retry_after", 1)
            print(f"Rate limited. Retry after {retry}s")
            time.sleep(retry)
            continue

        if res.status_code >= 300:
            print("Send failed:", res.status_code, res.text)

        break


# ===== メイン処理 =====
def main():
    if not WEBHOOK_URL:
        print("Webhook URL not set")
        return

    state = load_state()
    sent_ids = set(state["sent_ids"])

    feed = feedparser.parse(RSS_URL)
    if not feed.entries:
        print("Feed empty")
        return

    # 初回実行時は送信しない
    if not STATE_FILE.exists():
        print("First run: skip sending")
        ids = [entry.id for entry in feed.entries[:CHECK_ENTRIES]]
        save_state({"sent_ids": ids})
        return

    new_count = 0

    for entry in feed.entries[:CHECK_ENTRIES]:
        entry_id = entry.id
        title = entry.title
        link = entry.link
        summary = entry.get("summary", "")

        if entry_id in sent_ids:
            continue

        print("Send:", title)
        send_discord(title, link, summary)

        sent_ids.add(entry_id)
        new_count += 1

        time.sleep(SEND_INTERVAL)

    if new_count > 0:
        trimmed = list(sent_ids)[-50:]
        save_state({"sent_ids": trimmed})
        print(f"{new_count} articles sent")
    else:
        print("No new articles")


if __name__ == "__main__":
    main()