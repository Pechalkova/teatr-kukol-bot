import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin


SITE = "https://puppet-minsk.by"
AFISHA = SITE + "/bilety/afisha"

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


def parse_afisha(html):

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    events = []

    date_re = re.compile(
        r"(\d{1,2}\.\d{1,2}\.\d{4})"
        r"\s+(\d{1,2}:\d{2})"
    )

    for element in soup.find_all("a", href=True):

        title = " ".join(
            element.get_text(
                " ",
                strip=True
            ).split()
        )

        href = urljoin(
            AFISHA,
            element["href"]
        )

        # Нас интересуют только ссылки билетной системы.
        if "tce.by/shows.html" not in href:
            continue

        # Ищем дату/время в ближайших родительских блоках.
        parent = element
        context = ""

        for _ in range(5):

            parent = parent.parent

            if not parent:
                break

            context = " ".join(
                parent.get_text(
                    " ",
                    strip=True
                ).split()
            )

            match = date_re.search(context)

            if match:
                break

        if not match:
            continue

        date_s, time_s = match.groups()

        events.append({
            "title": title,
            "date": date_s,
            "time": time_s,
            "url": href,
        })

    # Убираем дубли.
    unique = {}

    for event in events:

        key = (
            event["date"],
            event["time"],
            event["title"],
            event["url"]
        )

        unique[key] = event

    return list(unique.values())


def inspect_ticket_page(event):

    print()
    print("========================================")
    print(
        "EVENT:",
        event["date"],
        event["time"],
        "|",
        event["title"]
    )
    print(
        "URL:",
        event["url"]
    )

    try:

        response = session.get(
            event["url"],
            timeout=30
        )

        print(
            "TCE STATUS:",
            response.status_code
        )

        print(
            "TCE BYTES:",
            len(response.text)
        )

        if response.status_code != 200:
            return

        html_lower = response.text.lower()

        markers = [
            "#00ff00",
            "#008000",
            "#00a000",
            "#00b000",
            "#00c000",
            "#00d000",
            "#00e000",
            "#00f000",
            "rgb(0,255,0)",
            "rgb(0, 255, 0)",
            "rgba(0,255,0",
            "rgba(0, 255, 0",
            "green",
            "свобод",
            "available",
            "free",
            "seat",
            "мест",
        ]

        found = []

        for marker in markers:

            if marker in html_lower:
                found.append(marker)

        print(
            "MARKERS FOUND:",
            found
        )

        # Покажем несколько фрагментов HTML
        # вокруг слов seat / green / свобод.
        patterns = [
            "seat",
            "green",
            "свобод",
            "available",
            "мест",
        ]

        shown = 0

        for pattern in patterns:

            position = 0

            while True:

                position = html_lower.find(
                    pattern,
                    position
                )

                if position == -1:
                    break

                start = max(
                    0,
                    position - 250
                )

                end = min(
                    len(response.text),
                    position + 500
                )

                fragment = response.text[
                    start:end
                ]

                print()
                print(
                    "HTML FRAGMENT:",
                    pattern
                )
                print(fragment)

                shown += 1

                position += len(pattern)

                if shown >= 5:
                    return

    except Exception as error:

        print(
            "TCE ERROR:",
            repr(error)
        )


def main():

    response = session.get(
        AFISHA,
        timeout=30
    )

    response.raise_for_status()

    print(
        "AFISHA:",
        response.status_code,
        "bytes=",
        len(response.text)
    )

    events = parse_afisha(
        response.text
    )

    print(
        "EVENTS FOUND:",
        len(events)
    )

    for event in events:

        print(
            "FOUND:",
            event["date"],
            event["time"],
            "|",
            event["title"],
            "|",
            event["url"]
        )

    # Проверяем первые 5 спектаклей.
    print()
    print("===== CHECKING TCE PAGES =====")

    for event in events[:5]:

        inspect_ticket_page(
            event
        )


if __name__ == "__main__":
    main()
