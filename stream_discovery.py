from pathlib import Path
from time import monotonic
from urllib.parse import urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


DEFAULT_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)
DEBUG_DIR = Path("debug")


def _validate_public_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("შეიყვანეთ სწორი Myvideo.ge არქივის ბმული.")


def discover_hls_stream_url(page_url, wait_seconds=120, headless=True, progress=None):
    """
    Opens the page in a normal browser context and captures HLS URLs requested
    by the video player. This does not bypass access controls; the page must be
    publicly accessible to the current machine.
    """
    _validate_public_url(page_url)
    captured_urls = []
    debug_urls = []
    all_urls = []
    final_page_url = page_url

    if progress:
        progress("ბრაუზერი ხსნის არქივის გვერდს და ეძებს ვიდეო ნაკადს...")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)

        context = browser.new_context(
            user_agent=DEFAULT_BROWSER_UA,
            locale="ka-GE",
            timezone_id="Asia/Tbilisi",
            viewport={"width": 1366, "height": 768},
        )
        page = context.new_page()

        def capture_url(url):
            all_urls.append(url)
            lower_url = url.lower()
            if any(marker in lower_url for marker in [".m3u8", "m3u8", ".mpd", ".ts", "playlist", "manifest"]):
                debug_urls.append(url)
            if "m3u8" in lower_url and url not in captured_urls:
                captured_urls.append(url)

        page.on("request", lambda request: capture_url(request.url))
        page.on("response", lambda response: capture_url(response.url))

        try:
            page.goto(page_url, wait_until="domcontentloaded", timeout=180000)
            final_page_url = page.url
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except PlaywrightTimeoutError:
                pass

            if not headless and progress:
                progress(
                    "ხილული ბრაუზერი გაიხსნა. დააჭირეთ Play-ს ზუსტად იმ ვიდეოზე, რომელიც გინდათ; სისტემა ქსელში ეძებს .m3u8 ნაკადს..."
                )
            else:
                # In headless mode we try conservative player-only clicks.
                for selector in [
                    "video",
                    "button[aria-label*=Play]",
                    "button[aria-label*=play]",
                    ".plyr__control",
                    ".vjs-big-play-button",
                ]:
                    try:
                        element = page.locator(selector).first
                        if element.count() > 0:
                            element.click(timeout=3000)
                            break
                    except Exception:
                        continue

                try:
                    page.mouse.click(683, 384)
                except Exception:
                    pass

            deadline = monotonic() + wait_seconds
            last_update = 0
            while monotonic() < deadline:
                if captured_urls:
                    break

                remaining = int(deadline - monotonic())
                if progress and remaining != last_update and remaining % 10 == 0:
                    progress(f"ვიდეო ნაკადის ძებნა... დარჩა დაახლოებით {remaining} წამი")
                    last_update = remaining

                page.wait_for_timeout(1000)
                final_page_url = page.url
        finally:
            if not captured_urls:
                DEBUG_DIR.mkdir(exist_ok=True)
                (DEBUG_DIR / "last_network_urls.txt").write_text(
                    "\n".join(dict.fromkeys(debug_urls[-300:])),
                    encoding="utf-8",
                )
                (DEBUG_DIR / "last_network_all_urls.txt").write_text(
                    "\n".join(dict.fromkeys(all_urls[-500:])),
                    encoding="utf-8",
                )
                try:
                    page.screenshot(path=str(DEBUG_DIR / "last_page.png"), full_page=True)
                except Exception:
                    pass
                try:
                    (DEBUG_DIR / "last_page.html").write_text(page.content(), encoding="utf-8")
                except Exception:
                    pass
            context.close()
            browser.close()

    if not captured_urls:
        raise RuntimeError(
            "ვიდეოს .m3u8 ნაკადი ვერ მოიძებნა. "
            f"ბრაუზერში საბოლოოდ გაიხსნა: {final_page_url}. "
            "თუ გვერდი ავტორიზაციას ან დამატებით დაცვას ითხოვს, საჭიროა ოფიციალური წვდომა "
            "ან ზუსტი არქივის/player URL."
        )

    # Prefer master playlists when available.
    captured_urls.sort(key=lambda url: ("/index" in url or "master" in url, len(url)), reverse=True)
    if progress:
        progress("ვიდეო ნაკადი მოიძებნა. FFmpeg ქმნის სამუშაო მონაკვეთს...")
    return captured_urls[0], {"User-Agent": DEFAULT_BROWSER_UA, "Referer": page_url}
