import os
import requests
from bs4 import BeautifulSoup


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


def main():

    response = requests.get(
        AFISHA,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    print(
        "AFISHA DEBUG:",
        response.status_code,
        "bytes=",
        len(response.text)
    )

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    print("\n===== LINKS WITH DATE/TIME =====")

    found = 0

    for element in soup.find_all(True):

        text = " ".join(
            element.get_text(
                " ",
                strip=True
            ).split()
        )

        if not text:
            continue

        if "." not in text or ":" not in text:
            continue

        if not any(
            digit in text
            for digit in "0123456789"
        ):
            continue

        # Показываем только относительно короткие
        # куски текста, где потенциально находится
        # дата/время спектакля.
        if len(text) > 500:
            continue

        links = element.find_all(
            "a",
            href=True
        )

        if not links:
            continue

        print("\nBLOCK:")
        print(text)

        for link in links:

            href = link.get("href", "")
            title = " ".join(
                link.get_text(
                    " ",
                    strip=True
                ).split()
            )

            print(
                "  LINK:",
                title,
                "=>",
                href
            )

        found += 1

        if found >= 30:
            break

    print(
        "\nTOTAL BLOCKS:",
        found
    )


if __name__ == "__main__":
    main()
