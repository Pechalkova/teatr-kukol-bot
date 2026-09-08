import os
import re
import json
import base64
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


SITE = "https://puppet-minsk.by"

# Страница, где находятся билеты и афиша
AFISHA = SITE + "/bilety/afisha"

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
REPO = os.environ["GITHUB_REPOSITORY"]
GH_TOKEN = os.environ["GITHUB_TOKEN"]

STATE_FILE = "state.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    )
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

    return session.request(
        method,
        url,
        headers=headers,
        timeout=30,
        **kwargs
    )


def load_state():
    url = (
        f"https://api.github.com/repos/"
        f"{REPO}/contents/{STATE_FILE}"
    )

    r = github_api("GET", url)

    if r.status_code == 200:
        data = r.json()

        raw = base64.b64decode(
            data["content"]
        ).decode("utf-8")

        state = json.loads(raw)

        state["_sha"] = data["sha"]

        # На случай, если в старом state
        # какого-то поля ещё нет.
        state.setdefault("subscribers", [])
        state.setdefault("offset", 0)
        state.setdefault("events", {})

        return state

    if r.status_code == 404:
        return {
            "subscribers": [],
            "offset": 0,
            "events": {}
        }

    raise RuntimeError(
        f"GitHub state read failed: "
        f"{r.status_code}"
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

    url = (
        f"https://api.github.com/repos/"
        f"{REPO}/contents/{STATE_FILE}"
    )

    r = github_api(
        "PUT",
        url,
        json=payload
    )

    if not r.ok:
        raise RuntimeError(
            f"GitHub state write failed: "
            f"{r.status_code}"
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
        text = (
            message.get("text") or ""
        ).strip()

        if chat_id and text.startswith("/start"):

            if chat_id not in state["subscribers"]:
                state["subscribers"].append(chat_id)

            tg(
                "sendMessage",
                {
                    "chat_id": chat_id,
                    "text": (
                        "Готово! 🎭\n\n"
                        "Я буду проверять билеты "
                        "Театра кукол и сообщать, "
                        "когда появятся свободные места."
                    )
                }
            )

    return state


def parse_event_list(html):
    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    result = {}

    # Поддерживаем:
    # 04.10.2026 11:15
    # 4.10.2026 11:15
    # 04.10.2026 в 11:15
    date_re = re.compile(
        r"\b(\d{1,2}\.\d{1,2}\.\d{4})"
        r"\s+(?:в\s+)?"
        r"(\d{1,2}:\d{2})\b"
    )

    site_host = urlparse(SITE).netloc

    for a in soup.find_all(
        "a",
        href=True
    ):

        href = urljoin(
            AFISHA,
            a["href"]
        )

        parsed = urlparse(href)

        # Не уходим на сторонние сайты.
        if (
            parsed.netloc
            and parsed.netloc != site_host
        ):
            continue

        # Не рассматриваем саму страницу афиши
        # и прочие служебные ссылки.
        if parsed.path.rstrip("/") in (
            "",
            "/afisha",
            "/bilety",
            "/bilety/afisha",
        ):
            continue

        title = " ".join(
            a.get_text(
                " ",
                strip=True
            ).split()
        )

        # Ищем дату и время в родительском
        # блоке ссылки.
        parent = a
        context = ""

        for _ in range(10):

            parent = parent.parent

            if not parent:
                break

            context = " ".join(
                parent.get_text(
                    " ",
                    strip=True
                ).split()
            )

            if date_re.search(context):
                break

        match = date_re.search(context)

        if not match:
            continue

        date_s, time_s = match.groups()

        key = href.split(
            "#",
            1
        )[0]

        # Иногда ссылка может вести
        # не непосредственно на билет,
        # а на внутреннюю страницу.
        if key == AFISHA:
            continue

        # Название спектакля.
        if not title or len(title) < 2:
            title = "Спектакль"

        result[key] = {
            "title": title,
            "date": date_s,
            "time": time_s,
            "url": key,
        }

    return list(result.values())


def page_has_available_seat(html):
    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    text = soup.get_text(
        " ",
        strip=True
    ).lower()

    # Явные признаки отсутствия мест.
    sold_out = [
        "мест нет",
        "нет мест",
        "билетов нет",
        "распродано",
        "sold out",
    ]

    if any(
        word in text
        for word in sold_out
    ):
        return False

    # Свободные места на схеме,
    # по твоему скриншоту, обозначаются зелёным.
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

        "rgba(0, 255, 0",
        "rgba(0,255,0",

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
            for key, value
            in element.attrs.items()
        ).lower()

        # Проверяем только элементы,
        # похожие на места.
        if not any(
            marker in attrs
            for marker in seat_markers
        ):
            continue

        # Ищем зелёный/свободный маркер.
        if any(
            marker in attrs
            for marker in green_markers
        ):
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

    print(
        f"AFISHA DEBUG: "
        f"status={response.status_code}; "
        f"bytes={len(response.text)}; "
        f"events={len(events)}"
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

        # Уведомляем только при переходе:
        # НЕ было мест -> появились места.
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

        state["events"][
            event["url"]
        ] = new

    save_state(state)

    print(
        f"Checked {len(events)} events; "
        f"subscribers="
        f"{len(state['subscribers'])}"
    )


if __name__ == "__main__":
    main()
