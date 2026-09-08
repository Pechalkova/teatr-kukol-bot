import os
import re
import json
import base64
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

SITE = "https://puppet-minsk.by"
AFISHA = SITE + "/afisha"

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
REPO = os.environ["GITHUB_REPOSITORY"]
GH_TOKEN = os.environ["GITHUB_TOKEN"]

STATE_FILE = "state.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (ticket-checker)"
}

session = requests.Session()
session.headers.update(HEADERS)


def github_api(method, url, **kwargs):
    headers = kwargs.pop("headers", {})
    headers.update({
        "Authorization": f"Bearer {GH_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    return session.request(method, url, headers=headers, timeout=30, **kwargs)


def load_state():
    url = f"https://api.github.com/repos/{REPO}/contents/{STATE_FILE}"
    r = github_api("GET", url)

    if r.status_code == 200:
        data = r.json()
        raw = base64.b64decode(data["content"]).decode("utf-8")
        state = json.loads(raw)
        state["_sha"] = data["sha"]
        return state

    if r.status_code == 404:
        return {
            "subscribers": [],
            "offset": 0,
            "events": {}
        }

    raise RuntimeError(
        f"GitHub state read failed: {r.status_code}"
    )


def save_state(state):
    sha = state.pop("_sha", None)

    content = json.dumps(
        state,
        ensure_ascii=False,
        indent=2
    )

    payload = {
        "message": "Update bot state",
        "content": base64.b64encode(
            content.encode("utf-8")
        ).decode("ascii"),
        "branch": "main",
    }

    if sha:
        payload["sha"] = sha

    url = f"https://api.github.com/repos/{REPO}/contents/{STATE_FILE}"

    r = github_api(
        "PUT",
        url,
        json=payload
    )

    if not r.ok:
        raise RuntimeError(
            f"GitHub state write failed: {r.status_code}"
        )


def tg(method, payload=None):
    url = (
        f"https://api.telegram.org/"
        f"bot{BOT_TOKEN}/{method}"
    )

    r = session.post(
        url,
        json=payload or {},
        timeout=30
    )

    r.raise_for_status()

    data = r.json()

    if not data.get("ok"):
        raise RuntimeError(str(data))

    return data["result"]


def process_telegram_updates(state):
    offset = state.get("offset", 0)

    updates = tg(
        "getUpdates",
        {
            "offset": offset,
            "timeout": 0,
            "allowed_updates": ["message"]
        }
    )

    for update in updates:
        state["offset"] = max(
            state.get("offset", 0),
            update["update_id"] + 1
        )

        message = update.get("message") or {}
        chat = message.get("chat") or {}

        chat_id = chat.get("id")
        text = (message.get("text") or "").strip()

        if chat_id and text.startswith("/start"):
            if chat_id not in state["subscribers"]:
                state["subscribers"].append(chat_id)

            tg(
                "sendMessage",
                {
                    "chat_id": chat_id,
                    "text": (
                        "Готово! 🎭\n\n"
                        "Я буду проверять афишу "
                        "Театра кукол и сообщать, "
                        "когда появятся места."
                    )
                }
            )

    return state

def parse_event_list(html):
    soup = BeautifulSoup(html, "html.parser")
    result = {}

    date_re = re.compile(
        r"\b(\d{2}\.\d{2}\.\d{4})\s+(\d{1,2}:\d{2})\b"
    )

    for a in soup.find_all("a", href=True):
        href = urljoin(AFISHA, a["href"])
        parsed = urlparse(href)

        if parsed.netloc and parsed.netloc != urlparse(SITE).netloc:
            continue

        title = " ".join(a.get_text(" ", strip=True).split())

        if not title or len(title) < 2:
            continue

        # Берём большой кусок текста вокруг ссылки.
        parent = a
        context = ""

        for _ in range(7):
            parent = parent.parent

            if not parent:
                break

            context = " ".join(
                parent.get_text(" ", strip=True).split()
            )

            if date_re.search(context):
                break

        match = date_re.search(context)

        if not match:
            continue

        date_s, time_s = match.groups()

        key = href.split("#", 1)[0]

        # Не добавляем служебные ссылки.
        if "/afisha" in key.rstrip("/"):
            continue

        result[key] = {
            "title": title,
            "date": date_s,
            "time": time_s,
            "url": key,
        }

    return list(result.values())


def page_has_available_seat(html):
    soup = BeautifulSoup(html, "html.parser")

    text = soup.get_text(" ", strip=True).lower()

    sold_out = [
        "мест нет",
        "нет мест",
        "билетов нет",
        "распродано",
        "sold out",
    ]

    if any(word in text for word in sold_out):
        return False

    green_markers = [
        "#00ff00",
        "#008000",
        "#00a000",
        "#00b000",
        "#00c000",
        "#00d000",
        "#00e000",
        "#00f000",
        "rgb(0, 255, 0)",
        "rgb(0,255,0)",
        "green",
        "свобод",
        "free",
        "available",
    ]

    seat_markers = [
        "seat",
        "мест",
        "data-seat",
        "data-status",
        "data-state",
    ]

    for element in soup.find_all(True):
        attrs = " ".join(
            f"{key}={value}"
            for key, value in element.attrs.items()
        ).lower()

        if not any(marker in attrs for marker in seat_markers):
            continue

        if any(marker in attrs for marker in green_markers):
            return True

    return False
def scan():
    response = session.get(
        AFISHA,
        timeout=30
    )

    response.raise_for_status()

    events = parse_event_list(
        response.text
    )

    results = []

    for event in events:

        try:
            page = session.get(
                event["url"],
                timeout=30
            )

            page.raise_for_status()

            available = page_has_available_seat(
                page.text
            )

        except Exception as error:
            print(
                "EVENT ERROR",
                event["url"],
                repr(error)
            )
            continue

        event["available"] = available
        results.append(event)

    return results


def main():

    state = load_state()

    state = process_telegram_updates(
        state
    )

    try:
        events = scan()

    except Exception as error:
        print(
            "AFISHA ERROR:",
            repr(error)
        )

        save_state(state)
        return

    for event in events:

        old = state["events"].get(
            event["url"],
            False
        )

        new = bool(
            event["available"]
        )

        if new and not old:

            message = (
                "🎟️ Похоже, появились места!\n\n"
                f"🎭 {event['title']}\n"
                f"📅 {event['date']} "
                f"{event['time']}\n\n"
                f"Открыть страницу:\n"
                f"{event['url']}"
            )

            for chat_id in list(
                state["subscribers"]
            ):

                try:
                    tg(
                        "sendMessage",
                        {
                            "chat_id": chat_id,
                            "text": message
                        }
                    )

                except Exception as error:
                    print(
                        "TELEGRAM ERROR",
                        chat_id,
                        repr(error)
                    )

        state["events"][event["url"]] = new

    save_state(state)

    print(
        f"Checked {len(events)} events; "
        f"subscribers="
        f"{len(state['subscribers'])}"
    )


if __name__ == "__main__":
    main()
