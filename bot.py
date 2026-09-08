import os, re, json
from datetime import datetime, timezone
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

AFISHA_URL = "https://puppet-minsk.by/afisha"
STATE_FILE = "state.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TheatreTicketMonitor/1.0)"}

def load_state():
    try:
        return json.loads(open(STATE_FILE, encoding="utf-8").read())
    except Exception:
        return {"events": {}, "initialized": False}

def save_state(s):
    Path(STATE_FILE).write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")

def fetch(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text

def parse_events(html):
    soup = BeautifulSoup(html, "html.parser")
    out, seen = [], set()
    for a in soup.find_all("a", href=True):
        title = " ".join(a.get_text(" ", strip=True).split())
        href = urljoin(AFISHA_URL, a["href"])
        if not title or "puppet-minsk.by" not in href or href.rstrip("/") == AFISHA_URL.rstrip("/"):
            continue
        parent = " ".join(a.parent.get_text(" ", strip=True).split()) if a.parent else ""
        m = re.search(r"(\d{2}\.\d{2}\.\d{4})\s+(\d{1,2}:\d{2})", parent)
        if m:
            date_s, time_s = m.groups()
            key = f"{date_s} {time_s} {href}"
            if key not in seen:
                seen.add(key)
                out.append({"key": key, "title": title, "date": date_s, "time": time_s, "url": href})
    return out

def available(html):
    text = " ".join(BeautifulSoup(html, "html.parser").stripped_strings).lower()
    sold = ["нет билетов", "билетов нет", "мест нет", "места закончились", "распродано", "sold out", "нет свободных мест"]
    if any(x in text for x in sold):
        return False
    buy = ["купить билет", "выбрать место", "выберите место", "в корзину", "оформить заказ"]
    if any(x in text for x in buy):
        return True
    return False

def send(token, chat_id, text):
    r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      data={"chat_id": chat_id, "text": text}, timeout=30)
    r.raise_for_status()

def main():
    token, chat_id = os.environ["TELEGRAM_BOT_TOKEN"], os.environ["TELEGRAM_CHAT_ID"]
    events, state = parse_events(fetch(AFISHA_URL)), load_state()
    current, messages = {}, []
    for e in events:
        try:
            ok = available(fetch(e["url"]))
        except Exception as exc:
            print("ERROR", e["url"], exc)
            continue
        current[e["key"]] = ok
        if state.get("initialized") and ok and not state["events"].get(e["key"], False):
            messages.append(f"🎭 Появились билеты!\n{e['title']}\n📅 {e['date']} {e['time']}\n🔗 {e['url']}")
    for msg in messages:
        send(token, chat_id, msg)
    state.update(events=current, initialized=True, checked_at=datetime.now(timezone.utc).isoformat())
    save_state(state)
    print(f"Checked {len(events)} events; notifications: {len(messages)}")

if __name__ == "__main__":
    main()
