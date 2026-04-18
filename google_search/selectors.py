"""CSS selectors for Google SERP features.

Each feature has a list of selectors ordered by reliability.
Google frequently changes class names, so multiple fallbacks
ensure extraction survives DOM updates.
"""

# ── Organic results ────────────────────────────────────────────────────────

ORGANIC_CONTAINER = [
    "div#rso div.MjjYud",
    "div#rso div.g",
    "div#search div.g",
]
ORGANIC_TITLE = ["h3"]
ORGANIC_LINK = [
    "a.zReHs[href]",
    "a[jsname='UWckNb'][href]",
    "a[data-ved][href]",
    "a[href]:not([href^='#']):not([href^='/'])",
]
ORGANIC_DESCRIPTION = [
    "div.VwiC3b",
    "div[data-sncf='1']",
    "div[style='-webkit-line-clamp:2']",
    "span.aCOpRe",
]
ORGANIC_DISPLAYED_URL = [
    "cite",
    "span.VuuXrf",
]
ORGANIC_DATE = [
    "span.LEwnzc span",
    "span.f",
]
ORGANIC_SITELINKS = [
    "div.HiHjCd a",
    "table.jmjoTe a",
    "div.usJj9c a",
]

# ── Featured snippet ───────────────────────────────────────────────────────

SNIPPET_CONTAINER = [
    "div.xpdopen div.ifM9O",
    "div.g div.xpdopen",
    "block-component div[data-attrid='wa:/description']",
]
SNIPPET_CONTENT = [
    "span.hgKElc",
    "div.LGOjhe span",
]
SNIPPET_LIST_ITEMS = [
    "div.ifM9O ol li",
    "div.ifM9O ul li",
]
SNIPPET_TITLE = ["a h3", "h3"]
SNIPPET_LINK = ["a[href]"]

# ── People Also Ask ────────────────────────────────────────────────────────

PAA_CONTAINER = [
    "div[jsname='yEVEwb']",
    "div.related-question-pair",
    "div[data-sgrd='true']",
]
PAA_QUESTION = [
    "span.CSkcDe",
    "div[data-q]",
    "div[role='button'] span",
]

# ── Knowledge panel ────────────────────────────────────────────────────────

KP_CONTAINER = [
    "div.kp-wholepage",
    "div.liYKde",
    "div[data-attrid='title']",
]
KP_TITLE = [
    "div[data-attrid='title'] span",
    "h2[data-attrid='title']",
    "div.kp-wholepage h2 span",
]
KP_SUBTITLE = [
    "div[data-attrid='subtitle'] span",
    "div.kp-wholepage div[data-attrid='subtitle']",
]
KP_DESCRIPTION = [
    "div.kno-rdesc span",
    "div[data-attrid='description'] span",
]
KP_ATTRIBUTES = [
    "div.kp-wholepage div[data-attrid]:not([data-attrid='title']):not([data-attrid='subtitle']):not([data-attrid='description'])",
]

# ── Ads ────────────────────────────────────────────────────────────────────

AD_TOP_CONTAINER = [
    "div#tads div[data-text-ad]",
    "div#tads div.uEierd",
]
AD_BOTTOM_CONTAINER = [
    "div#tadsb div[data-text-ad]",
    "div#tadsb div.uEierd",
]
AD_TITLE = [
    "div[role='heading']",
    "span.cfxYMc",
]
AD_LINK = [
    "a[data-rw]",
    "a[data-pcu]",
]
AD_DISPLAYED_URL = [
    "span.Zu0yb",
    "cite",
]
AD_DESCRIPTION = [
    "div.yDYNvb",
    "div.MUxGbd",
]

# ── Local pack ─────────────────────────────────────────────────────────────

LOCAL_CONTAINER = [
    "div.VkpGBb",
    "div[data-local-attribute]",
    "div.cXedhc a",
]
LOCAL_NAME = [
    "span.OSrXXb",
    "div.dbg0pd",
    "span.fZkJlf",
]
LOCAL_RATING = [
    "span.yi40Hd",
    "span.BTtC6e",
]
LOCAL_REVIEWS = [
    "span.RDApEe",
    "span.HypWnf",
]
LOCAL_ADDRESS = [
    "div.rllt__details div:nth-child(3)",
    "div.rllt__wrapped",
]
LOCAL_CATEGORY = [
    "div.rllt__details div:first-child span",
]

# ── Video carousel ─────────────────────────────────────────────────────────

VIDEO_CONTAINER = [
    "div.RzdJxc",
    "g-inner-card",
    "div[jscontroller] div.ct3b9e",
]
VIDEO_TITLE = [
    "div.fc9yUc",
    "span.cHaqb",
    "div.mCBkyc",
]
VIDEO_LINK = [
    "a[href]",
]
VIDEO_SOURCE = [
    "span.pcJO7e",
    "cite",
]
VIDEO_DURATION = [
    "div.J1mWY",
    "span.wIdWue",
]
VIDEO_DATE = [
    "span.rjmdhd",
    "div.hmBe4e",
]

# ── Related searches ───────────────────────────────────────────────────────

RELATED_CONTAINER = [
    "div#brs",
    "div#botstuff div.y6Uyqe",
]
RELATED_QUERY = [
    "a div.s75CSd b",
    "a",
    "a.k8XOCe",
]

# ── Meta / result stats ───────────────────────────────────────────────────

RESULT_STATS = [
    "div#result-stats",
    "div#slim_appbar",
]

# ── Consent dialog ─────────────────────────────────────────────────────────

CONSENT_BUTTON_TEXTS = [
    "Accept all",
    "Reject all",
    "Alle akzeptieren",
    "Tout accepter",
    "Aceptar todo",
    "Accetta tutto",
]

# ── CAPTCHA detection ──────────────────────────────────────────────────────

CAPTCHA_INDICATORS = [
    "form#captcha-form",
    "div#recaptcha",
    "div.g-recaptcha",
    "iframe[src*='recaptcha']",
]
