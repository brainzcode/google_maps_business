"""Stealth browser setup and anti-detection helpers."""

from __future__ import annotations

import logging
import random
from typing import Optional

from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Playwright,
)
from playwright_stealth import Stealth

from google_maps.config import ScraperConfig
from google_maps.proxy import Proxy

logger = logging.getLogger(__name__)

# Stealth config — patches navigator.webdriver, chrome.runtime, plugins,
# permissions, languages, WebGL vendor, user-agent data, and more.
_stealth = Stealth(
    navigator_webdriver=True,
    chrome_app=True,
    chrome_csi=True,
    chrome_load_times=True,
    chrome_runtime=False,  # can break some sites
    navigator_plugins=True,
    navigator_permissions=True,
    navigator_languages=True,
    navigator_platform=True,
    navigator_vendor=True,
    navigator_user_agent=True,
    navigator_user_agent_data=True,
    webgl_vendor=True,
    media_codecs=True,
    iframe_content_window=True,
    hairline=True,
    error_prototype=True,
    sec_ch_ua=True,
)


async def launch(
    config: ScraperConfig,
    proxy: Optional[Proxy] = None,
) -> tuple[Playwright, Browser, BrowserContext]:
    """Launch a stealth Chromium browser with an attached context.

    Anti-detection measures applied:
        - playwright-stealth patches (20+ evasion scripts)
        - randomised user-agent from config pool
        - realistic viewport with slight random variation
        - optional proxy routing (credentials kept out of URL)
        - disabled Blink automation flags
    """
    pw = await async_playwright().start()

    launch_args = [
        "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage",
        "--no-first-run",
        "--no-default-browser-check",
    ]

    launch_kwargs: dict = {
        "headless": config.headless,
        "args": launch_args,
    }

    if proxy is not None:
        launch_kwargs["proxy"] = proxy.as_playwright_dict()
        logger.info("Routing through proxy %s", proxy)

    browser = await pw.chromium.launch(**launch_kwargs)
    context = await _new_context(browser, config)
    return pw, browser, context


async def _new_context(browser: Browser, config: ScraperConfig) -> BrowserContext:
    """Create a fresh stealth context on an already-launched browser."""
    # Slight viewport randomisation to avoid fingerprinting
    width = 1920 + random.randint(-20, 20)
    height = 1080 + random.randint(-10, 10)
    ua = random.choice(config.user_agents)

    context = await browser.new_context(
        viewport={"width": width, "height": height},
        locale=config.locale,
        user_agent=ua,
        java_script_enabled=True,
        timezone_id="America/Chicago",
    )
    await _stealth.apply_stealth_async(context)
    return context


async def relaunch(
    pw: Playwright,
    old_browser: Browser,
    config: ScraperConfig,
    proxy: Optional[Proxy],
) -> tuple[Browser, BrowserContext]:
    """Close `old_browser` and launch a fresh one with the new proxy.

    Used when rotating proxies mid-session — Playwright applies proxy settings
    at browser launch, not per-context, so a fresh process is required.
    """
    try:
        await old_browser.close()
    except Exception:
        pass  # already closed / crashed — not fatal

    launch_args = [
        "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    launch_kwargs: dict = {"headless": config.headless, "args": launch_args}
    if proxy is not None:
        launch_kwargs["proxy"] = proxy.as_playwright_dict()
        logger.info("Rotating to proxy %s", proxy)

    browser = await pw.chromium.launch(**launch_kwargs)
    context = await _new_context(browser, config)
    return browser, context
