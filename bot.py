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

SENT_FILE = Path("sent_links.json")
SEND_INTERVAL = 0.7
MAX_LINKS = 1000
CHECK_ENTRIES = 3


# ===== URL正規化 =====
def normalize_url(url: str):
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


# ===== 永続化 =====
def load_sent_links():
    if SENT_FILE.exists():
        with open(SENT_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_sent_links(links):
    trimmed = list(links)[-MAX_LINKS:]
    with open(SENT_FILE, "w", encoding="utf-8") as f:
        json.dump(trimmed, f, ensure_ascii=False, indent=2)


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

    sent_links = load_sent_links()

    feed = feedparser.parse(RSS_URL)
    if not feed.entries:
        print("Feed empty")
        return

    # 初回実行時は送信しない
    if not SENT_FILE.exists():
        print("First run: skip sending")
        links = {normalize_url(entry.link) for entry in feed.entries[:CHECK_ENTRIES]}
        save_sent_links(links)
        return

    new_count = 0

    for entry in feed.entries[:CHECK_ENTRIES]:
        title = entry.title
        link = entry.link
        summary = entry.get("summary", "")

        normalized = normalize_url(link)

        if normalized in sent_links:
            continue

        print("Send:", title)

        send_discord(title, link, summary)

        sent_links.add(normalized)
        new_count += 1

        time.sleep(SEND_INTERVAL)

    if new_count > 0:
        save_sent_links(sent_links)
        print(f"{new_count} articles sent")
    else:
        print("No new articles")


if __name__ == "__main__":
    main()