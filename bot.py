import requests

TEST_URL = "https://tce.by/shows.html?base=RkZDMTE2MUQtMTNFNy00NUIyLTg0QzYtMURDMjRBNTc1ODA0&data=4967"

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://puppet-minsk.by/bilety/afisha",
    "Connection": "close",
}

print("========================================")
print("TEST TCE")
print("========================================")
print("URL:")
print(TEST_URL)
print()

try:
    session = requests.Session()
    session.headers.update(headers)

    print("Отправляем запрос...")

    response = session.get(
        TEST_URL,
        timeout=20,
        allow_redirects=True,
    )

    print()
    print("STATUS:", response.status_code)
    print("FINAL URL:", response.url)
    print("BYTES:", len(response.content))
    print("ENCODING:", response.encoding)
    print("APPARENT ENCODING:", response.apparent_encoding)
    print()

    print("HEADERS:")
    for key, value in response.headers.items():
        print(f"{key}: {value}")

    print()
    print("FIRST 1000 CHARACTERS:")
    print("----------------------------------------")

    try:
        text = response.content.decode("utf-8", errors="replace")
    except Exception:
        text = response.text

    print(text[:1000])

except Exception as e:
    print()
    print("ERROR:")
    print(repr(e))

print()
print("========================================")
print("TEST FINISHED")
print("========================================")
