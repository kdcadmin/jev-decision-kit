"""Record a 9:16 product demo of the live 技能柜. Output stays local."""
from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
URL = "http://127.0.0.1:8765/"
CAP_JS = """
(t) => {
  let el = document.getElementById("dy-cap");
  if (!el) {
    el = document.createElement("div");
    el.id = "dy-cap";
    el.style.cssText = [
      "position:fixed",
      "left:32px",
      "right:32px",
      "bottom:96px",
      "z-index:99999",
      "pointer-events:none",
      "font-weight:900",
      "font-size:68px",
      "line-height:1.08",
      "letter-spacing:-0.05em",
      "color:#fff",
      "text-shadow:0 4px 0 #111, 0 14px 28px rgba(0,0,0,.5)",
      "font-family:'Noto Sans SC','Microsoft YaHei',sans-serif"
    ].join(";");
    document.body.appendChild(el);
    const mark = document.createElement("div");
    mark.textContent = "内容由 AI 生成";
    mark.style.cssText = "position:fixed;left:32px;bottom:52px;z-index:99999;pointer-events:none;color:#222;font:700 18px 'Noto Sans SC',sans-serif;opacity:.55";
    document.body.appendChild(mark);
  }
  el.textContent = t;
}
"""


def main() -> None:
    out_dir = HERE / "_rec"
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*"):
        old.unlink()
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        context = browser.new_context(
            viewport={"width": 1080, "height": 1920},
            device_scale_factor=1,
            record_video_dir=str(out_dir),
            record_video_size={"width": 1080, "height": 1920},
        )
        page = context.new_page()
        page.goto(URL, wait_until="domcontentloaded")
        page.wait_for_selector("#task")
        page.wait_for_selector("#list [data-name]", timeout=20000)
        page.wait_for_timeout(800)
        page.evaluate(CAP_JS, "我做了个技能柜")
        page.wait_for_timeout(1800)
        page.evaluate(CAP_JS, "一句话，开口之前先选")
        page.wait_for_timeout(900)
        page.click("#task")
        page.fill("#task", "")
        page.type("#task", "把这次会议整理成纪要", delay=70)
        page.wait_for_timeout(400)
        page.click("#go")
        page.wait_for_selector(".ticket-card", timeout=20000)
        page.wait_for_timeout(600)
        page.evaluate(CAP_JS, "点了名才留下")
        page.wait_for_timeout(2800)
        page.evaluate(CAP_JS, "没点名关掉")
        page.wait_for_timeout(1600)
        page.locator(".cats button").first.click()
        page.wait_for_timeout(400)
        page.fill("#task", "")
        page.evaluate(CAP_JS, "现在几点了")
        page.type("#task", "现在几点了", delay=70)
        page.click("#go")
        page.wait_for_timeout(1400)
        page.wait_for_selector(".ticket-card", timeout=20000)
        page.wait_for_timeout(800)
        page.evaluate(CAP_JS, "自己做")
        page.wait_for_timeout(2400)
        page.evaluate(CAP_JS, "有人用吗")
        page.wait_for_timeout(3200)
        page.evaluate(CAP_JS, "技能柜 · jev-decision")
        page.wait_for_timeout(2800)
        page.close()
        context.close()
        browser.close()
    clips = list(out_dir.glob("*.webm"))
    if not clips:
        raise SystemExit("no webm")
    dest = HERE / "oneshot-raw.webm"
    clips[0].replace(dest)
    print(dest)


if __name__ == "__main__":
    main()
