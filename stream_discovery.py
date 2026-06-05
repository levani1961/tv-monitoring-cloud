import json
import os
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
        raise ValueError("შეიყვანეთ სწორი ვიდეო ან არქივის ბმული.")


def discover_hls_stream_url(page_url, wait_seconds=120, headless=True, progress=None):
    _validate_public_url(page_url)
    
    # თუ ლინკი არის YouTube-ის, ვიყენებთ პირდაპირ ნაკადს ბრაუზერის გარეშე
    if "youtube.com" in page_url or "youtu.be" in page_url:
        if progress:
            progress("აღმოჩენილია YouTube ლინკი. ნაკადის ოპტიმიზაცია...")
        # იუთუბის შემთხვევაში პირდაპირ ვაბრუნებთ თავის ლინკს, რადგან FFmpeg მას კითხულობს
        return page_url, {"User-Agent": DEFAULT_BROWSER_UA}

    captured_urls = []
    debug_urls = []
    all_urls = []
    final_page_url = page_url

    if progress:
        progress("ბრაუზერი ხსნის Myvideo არქივს და ეძებს ვიდეო ნაკადს...")

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

            for selector in [
                "video", "button[aria-label*=Play]", "button[aria-label*=play]",
                ".plyr__control", ".vjs-big-play-button"
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
            while monotonic() < deadline:
                if captured_urls:
                    break
                page.wait_for_timeout(1000)
                final_page_url = page.url
        finally:
            context.close()
            browser.close()

    if not captured_urls:
        raise RuntimeError(
            "ვიდეოს .m3u8 ნაკადი ვერ მოიძებნა. "
            f"ბრაუზერში საბოლოოდ გაიხსნა: {final_page_url}."
        )

    captured_urls.sort(key=lambda url: ("/index" in url or "master" in url, len(url)), reverse=True)
    return captured_urls[0], {"User-Agent": DEFAULT_BROWSER_UA, "Referer": page_url}

        progress("ვიდეო ნაკადი მოიძებნა. FFmpeg ქმნის სამუშაო მონაკვეთს...")
    return captured_urls[0], {"User-Agent": DEFAULT_BROWSER_UA, "Referer": page_url}
