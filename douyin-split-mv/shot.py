"""Grab stills at freeze times to judge the cut."""
from pathlib import Path

from playwright.sync_api import sync_playwright

from record import PORT, serve

HERE = Path(__file__).resolve().parent


def main():
    serve()
    times = [4.2, 12.0, 20.4, 27.0, 39.5]
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        page = browser.new_page(viewport={"width": 1080, "height": 1920})
        for t in times:
            page.goto(
                f"http://127.0.0.1:{PORT}/douyin-split-mv/index.html?t={t}",
                wait_until="load",
            )
            page.wait_for_timeout(500)
            out = HERE / f"_qa{int(t)}.png"
            page.screenshot(path=str(out), type="png")
            print(out)
        browser.close()


if __name__ == "__main__":
    main()
