"""Stealth browser setup with TLS fingerprint evasion and resource blocking.

Anti-detection strategy:
1. TLS Fingerprinting — Use channel="chrome" to launch the system Chrome
   binary instead of Playwright's bundled Chromium. Real Chrome has an
   authentic JA3/JA4 TLS fingerprint that matches millions of real users.
   Chromium's fingerprint is distinct and flagged by Google.
2. Cookie Warming — curl_cffi (with Chrome TLS impersonation) hits Google
   first to establish a session with authentic JA3/JA4. Those cookies are
   injected into Playwright so Google sees continuity from a "real" TLS
   session. This bridges the gap if Playwright falls back to Chromium.
3. Browser Fingerprinting — Comprehensive init scripts to patch navigator
   properties, WebGL, Canvas, Plugins, Permissions, and other fingerprint
   vectors that Google checks.
4. Behavioural — Randomised viewport, timezone matching locale, realistic
   user-agent strings, resource blocking for speed.
"""

import logging
import random

from curl_cffi import requests as cffi_requests
from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Playwright,
    Route,
)

from google_maps.proxy import Proxy
from google_search.config import SerpConfig

logger = logging.getLogger(__name__)

BLOCKED_RESOURCE_TYPES = {"image", "media", "font", "stylesheet"}

BLOCKED_DOMAINS = [
    "google-analytics.com",
    "googletagmanager.com",
    "doubleclick.net",
    "googlesyndication.com",
    "googleadservices.com",
    "facebook.net",
    "connect.facebook.com",
]

# Timezone mapping for common locales — TZ must match locale to avoid
# fingerprint inconsistencies that trigger bot detection.
LOCALE_TIMEZONES = {
    "en": "America/Chicago",
    "en-US": "America/New_York",
    "en-GB": "Europe/London",
    "en-AU": "Australia/Sydney",
    "de": "Europe/Berlin",
    "fr": "Europe/Paris",
    "es": "Europe/Madrid",
    "it": "Europe/Rome",
    "pt": "America/Sao_Paulo",
    "ja": "Asia/Tokyo",
    "ko": "Asia/Seoul",
    "zh": "Asia/Shanghai",
}

# Comprehensive stealth init script — patches all major fingerprint vectors.
# Each section targets a specific detection method used by Google/Cloudflare.
STEALTH_INIT_SCRIPT = """
// ── 1. WebDriver flag ─────────────────────────────────────────────
// Primary bot detection: navigator.webdriver is true for automated browsers.
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

// ── 2. Chrome runtime ─────────────────────────────────────────────
// Real Chrome exposes window.chrome with specific properties.
// Headless Chromium/Playwright doesn't have this by default.
if (!window.chrome) {
    window.chrome = {
        runtime: {
            onConnect: { addListener: function() {}, removeListener: function() {} },
            onMessage: { addListener: function() {}, removeListener: function() {} },
            connect: function() { return { onMessage: { addListener: function() {} }, postMessage: function() {} }; },
            sendMessage: function() {},
        },
        loadTimes: function() { return {}; },
        csi: function() { return {}; },
    };
}

// ── 3. Plugins array ──────────────────────────────────────────────
// Real Chrome reports plugins. An empty array signals headless.
Object.defineProperty(navigator, 'plugins', {
    get: () => {
        const plugins = [
            { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
            { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
            { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' },
        ];
        plugins.length = 3;
        return plugins;
    },
});

// ── 4. Languages ──────────────────────────────────────────────────
// navigator.languages must be consistent with Accept-Language header.
Object.defineProperty(navigator, 'languages', {
    get: () => ['en-US', 'en'],
});

// ── 5. Permissions API ────────────────────────────────────────────
// Headless Chrome returns 'denied' for notification permission query.
// Real Chrome returns 'prompt'. This is checked by detection scripts.
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications'
        ? Promise.resolve({ state: Notification.permission })
        : originalQuery(parameters)
);

// ── 6. WebGL vendor/renderer ──────────────────────────────────────
// Headless Chrome reports "Google SwiftShader" which is a known signal.
// We override to report a realistic GPU.
const getParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(parameter) {
    // UNMASKED_VENDOR_WEBGL
    if (parameter === 37445) return 'Google Inc. (Apple)';
    // UNMASKED_RENDERER_WEBGL
    if (parameter === 37446) return 'ANGLE (Apple, Apple M1 Pro, OpenGL 4.1)';
    return getParameter.call(this, parameter);
};

// Also patch WebGL2
if (typeof WebGL2RenderingContext !== 'undefined') {
    const getParameter2 = WebGL2RenderingContext.prototype.getParameter;
    WebGL2RenderingContext.prototype.getParameter = function(parameter) {
        if (parameter === 37445) return 'Google Inc. (Apple)';
        if (parameter === 37446) return 'ANGLE (Apple, Apple M1 Pro, OpenGL 4.1)';
        return getParameter2.call(this, parameter);
    };
}

// ── 7. Platform consistency ───────────────────────────────────────
// Ensure platform matches user-agent to avoid cross-signal detection.
Object.defineProperty(navigator, 'platform', {
    get: () => 'MacIntel',
});

// ── 8. Hardware concurrency ───────────────────────────────────────
// Report a realistic CPU core count (headless sometimes reports 1).
Object.defineProperty(navigator, 'hardwareConcurrency', {
    get: () => 8,
});

// ── 9. Device memory ─────────────────────────────────────────────
// Report realistic memory (headless may report 0 or undefined).
Object.defineProperty(navigator, 'deviceMemory', {
    get: () => 8,
});

// ── 10. Connection API ────────────────────────────────────────────
// Headless may not have this; real Chrome does.
if (!navigator.connection) {
    Object.defineProperty(navigator, 'connection', {
        get: () => ({
            effectiveType: '4g',
            rtt: 50,
            downlink: 10,
            saveData: false,
        }),
    });
}

// ── 11. Canvas fingerprint noise ──────────────────────────────────
// Add subtle noise to canvas operations to prevent exact fingerprint matching
// across sessions while still looking natural.
const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
HTMLCanvasElement.prototype.toDataURL = function(type) {
    if (type === 'image/png' || type === undefined) {
        const context = this.getContext('2d');
        if (context) {
            const imageData = context.getImageData(0, 0, this.width, this.height);
            for (let i = 0; i < imageData.data.length; i += 4) {
                // Tiny noise in alpha channel — invisible but changes fingerprint
                imageData.data[i + 3] = imageData.data[i + 3] > 0
                    ? Math.max(1, imageData.data[i + 3] + (Math.random() > 0.5 ? 1 : -1))
                    : 0;
            }
            context.putImageData(imageData, 0, 0);
        }
    }
    return origToDataURL.apply(this, arguments);
};
"""


def _proxy_url_for_curl(proxy: Proxy | None) -> str | None:
    """curl_cffi takes a single URL string with credentials embedded."""
    if proxy is None:
        return None
    if proxy.username is None:
        return proxy.server
    from urllib.parse import quote
    user = quote(proxy.username, safe="")
    pw = quote(proxy.password or "", safe="")
    scheme, _, host_port = proxy.server.partition("://")
    return f"{scheme}://{user}:{pw}@{host_port}"


def _warm_cookies(ua: str, proxy: Proxy | None = None) -> list[dict]:
    """Hit Google with curl_cffi to get cookies from an authentic TLS session.

    curl_cffi uses BoringSSL and impersonates Chrome's exact TLS fingerprint
    (JA3/JA4 hash, HTTP/2 SETTINGS, header order). This establishes a session
    that Google recognises as coming from real Chrome. The returned cookies
    are injected into Playwright so Google sees session continuity.
    """
    try:
        kwargs: dict = {
            "impersonate": "chrome",
            "headers": {
                "User-Agent": ua,
                "Accept-Language": "en-US,en;q=0.9",
            },
        }
        proxy_url = _proxy_url_for_curl(proxy)
        if proxy_url:
            kwargs["proxies"] = {"https": proxy_url, "http": proxy_url}

        session = cffi_requests.Session()
        resp = session.get("https://www.google.com/", **kwargs)

        cookies = []
        for c in session.cookies.jar:
            cookies.append({
                "name": c.name,
                "value": c.value,
                "url": "https://www.google.com/",
            })

        logger.debug("Warmed %d cookies via curl_cffi (status %d)", len(cookies), resp.status_code)
        return cookies
    except Exception as e:
        logger.warning("Cookie warming failed: %s — proceeding without", e)
        return []


async def _block_handler(route: Route) -> None:
    """Abort requests for unnecessary resources to speed up page loads."""
    if route.request.resource_type in BLOCKED_RESOURCE_TYPES:
        await route.abort()
        return

    url = route.request.url
    for domain in BLOCKED_DOMAINS:
        if domain in url:
            await route.abort()
            return

    await route.continue_()


async def launch(
    config: SerpConfig,
    proxy: Proxy | None = None,
) -> tuple[Playwright, Browser, BrowserContext]:
    """Launch a stealth Chrome browser with TLS fingerprint evasion.

    Anti-detection layers:
    1. TLS Fingerprint — channel="chrome" uses the real Chrome binary,
       producing an authentic JA3/JA4 hash identical to regular users.
    2. Browser Fingerprint — init scripts patch WebDriver, Chrome runtime,
       plugins, WebGL, canvas, permissions, and hardware signals.
    3. Behavioural — randomised viewport, locale-matched timezone,
       realistic user-agent, human-like delays (handled by scraper).
    4. Network — resource blocking hides automation patterns in
       request waterfalls and speeds up scraping.
    """
    pw = await async_playwright().start()

    launch_args = [
        "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-component-update",
        "--disable-background-networking",
        "--disable-default-apps",
    ]

    launch_kwargs: dict = {
        "headless": config.headless,
        "args": launch_args,
        # Use real Chrome for authentic TLS fingerprint (JA3/JA4).
        # Falls back to bundled Chromium if Chrome is not installed.
        "channel": "chrome",
    }

    if proxy is not None:
        launch_kwargs["proxy"] = proxy.as_playwright_dict()
        logger.info("Routing through proxy %s", proxy)
    elif config.proxy:
        # Backward-compat: legacy single-string proxy from config
        launch_kwargs["proxy"] = {"server": config.proxy}

    try:
        browser = await pw.chromium.launch(**launch_kwargs)
    except Exception:
        # Fallback to bundled Chromium if system Chrome unavailable
        del launch_kwargs["channel"]
        browser = await pw.chromium.launch(**launch_kwargs)

    # Slight viewport randomisation to avoid fingerprinting
    width = 1920 + random.randint(-40, 40)
    height = 1080 + random.randint(-20, 20)

    ua = random.choice(config.user_agents)

    # Match timezone to locale for fingerprint consistency
    tz = LOCALE_TIMEZONES.get(config.locale, "America/Chicago")

    context = await browser.new_context(
        viewport={"width": width, "height": height},
        locale=config.locale,
        user_agent=ua,
        java_script_enabled=True,
        timezone_id=tz,
        color_scheme="light",
        # Extra HTTP headers that real Chrome sends
        extra_http_headers={
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Ch-Ua": '"Chromium";v="125", "Google Chrome";v="125", "Not.A/Brand";v="24"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"macOS"',
        },
    )

    # Inject comprehensive stealth patches
    await context.add_init_script(STEALTH_INIT_SCRIPT)

    # Warm cookies via curl_cffi (authentic Chrome TLS fingerprint).
    # This ensures Google sees cookies from a real TLS session.
    cookies = _warm_cookies(ua, proxy)
    if cookies:
        await context.add_cookies(cookies)

    if config.block_resources:
        await context.route("**/*", _block_handler)

    return pw, browser, context


async def relaunch(
    pw: Playwright,
    old_browser: Browser,
    config: SerpConfig,
    proxy: Proxy | None,
) -> tuple[Browser, BrowserContext]:
    """Close `old_browser` and launch a fresh one with the new proxy.

    Used when rotating proxies mid-session — Playwright applies proxy
    settings at browser launch, not per-context, so a fresh process is
    required.
    """
    try:
        await old_browser.close()
    except Exception:
        pass

    launch_args = [
        "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-component-update",
        "--disable-background-networking",
        "--disable-default-apps",
    ]
    launch_kwargs: dict = {
        "headless": config.headless,
        "args": launch_args,
        "channel": "chrome",
    }
    if proxy is not None:
        launch_kwargs["proxy"] = proxy.as_playwright_dict()
        logger.info("Rotating to proxy %s", proxy)

    try:
        browser = await pw.chromium.launch(**launch_kwargs)
    except Exception:
        del launch_kwargs["channel"]
        browser = await pw.chromium.launch(**launch_kwargs)

    width = 1920 + random.randint(-40, 40)
    height = 1080 + random.randint(-20, 20)
    ua = random.choice(config.user_agents)
    tz = LOCALE_TIMEZONES.get(config.locale, "America/Chicago")

    context = await browser.new_context(
        viewport={"width": width, "height": height},
        locale=config.locale,
        user_agent=ua,
        java_script_enabled=True,
        timezone_id=tz,
        color_scheme="light",
        extra_http_headers={
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Ch-Ua": '"Chromium";v="125", "Google Chrome";v="125", "Not.A/Brand";v="24"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"macOS"',
        },
    )
    await context.add_init_script(STEALTH_INIT_SCRIPT)

    cookies = _warm_cookies(ua, proxy)
    if cookies:
        await context.add_cookies(cookies)

    if config.block_resources:
        await context.route("**/*", _block_handler)

    return browser, context
