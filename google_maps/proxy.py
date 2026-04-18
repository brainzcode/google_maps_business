"""Proxy parsing, pooling, and rotation.

Accepted proxy string formats:
    host:port
    host:port:user:pass
    user:pass@host:port
    scheme://host:port
    scheme://user:pass@host:port

Supported schemes: http, https, socks4, socks5. Default is http.

Example usage:
    pool = ProxyPool.from_strings(["http://u:p@1.2.3.4:8080", "5.6.7.8:3128"])
    proxy = pool.next()                 # rotation
    pool.mark_bad(proxy, "timeout")     # disable temporarily
    pool.mark_good(proxy)               # reset failure count
"""

from __future__ import annotations

import random
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Iterable, Optional
from urllib.parse import urlparse, unquote

_VALID_SCHEMES = {"http", "https", "socks4", "socks5"}

# Rotation strategies. See ProxyPool.next() for semantics.
ROTATION_STRATEGIES = ("round_robin", "random", "sticky")


@dataclass(frozen=True)
class Proxy:
    """A single proxy endpoint.

    `server` is the server URL Playwright expects (scheme://host:port, no auth).
    `username` and `password` are passed separately to Playwright so credentials
    never end up URL-encoded in request logs or error messages.
    """

    server: str
    username: Optional[str] = None
    password: Optional[str] = None

    def as_playwright_dict(self) -> dict:
        """Return the dict form Playwright's `proxy=` kwarg expects."""
        d: dict = {"server": self.server}
        if self.username is not None:
            d["username"] = self.username
        if self.password is not None:
            d["password"] = self.password
        return d

    @property
    def host_port(self) -> str:
        """Return `host:port` without scheme or credentials — safe for logs."""
        parsed = urlparse(self.server)
        return parsed.netloc or self.server

    def __str__(self) -> str:
        return self.host_port


def parse_proxy_string(raw: str) -> Proxy:
    """Turn a user-supplied proxy string into a :class:`Proxy`.

    Raises `ValueError` for empty / malformed input. Credentials are never
    embedded in the returned `server` URL — Playwright receives them via
    separate username/password keys so they stay out of stack traces.
    """
    if raw is None:
        raise ValueError("proxy string is None")
    s = raw.strip()
    if not s:
        raise ValueError("proxy string is empty")

    # Strip surrounding quotes users sometimes paste from shells
    if len(s) >= 2 and s[0] == s[-1] and s[0] in {'"', "'"}:
        s = s[1:-1].strip()

    scheme = "http"
    username: Optional[str] = None
    password: Optional[str] = None

    if "://" in s:
        scheme_part, rest = s.split("://", 1)
        scheme = scheme_part.lower().strip()
        if scheme not in _VALID_SCHEMES:
            raise ValueError(
                f"unsupported proxy scheme '{scheme}' — use one of {sorted(_VALID_SCHEMES)}"
            )
        s = rest

    # Colon-separated legacy form: host:port:user:pass
    if s.count(":") == 3 and "@" not in s:
        host, port, username, password = s.split(":", 3)
        username = unquote(username)
        password = unquote(password)
        host_port = f"{host}:{port}"
    else:
        if "@" in s:
            creds, host_port = s.rsplit("@", 1)
            if ":" in creds:
                username, password = creds.split(":", 1)
            else:
                username = creds
                password = ""
            username = unquote(username)
            password = unquote(password)
        else:
            host_port = s

    # Validate host:port
    if ":" not in host_port:
        raise ValueError(f"proxy missing port: {raw!r}")
    host, _, port = host_port.rpartition(":")
    host = host.strip("[]")  # IPv6 brackets
    if not host:
        raise ValueError(f"proxy missing host: {raw!r}")
    if not re.fullmatch(r"\d{1,5}", port):
        raise ValueError(f"proxy port not numeric: {raw!r}")
    port_n = int(port)
    if not (1 <= port_n <= 65535):
        raise ValueError(f"proxy port out of range (1-65535): {raw!r}")

    server = f"{scheme}://{host_port}"
    return Proxy(server=server, username=username, password=password)


def load_proxy_file(path: str) -> list[Proxy]:
    """Read a proxy-per-line text file.

    Blank lines and lines starting with `#` are ignored. Raises
    `FileNotFoundError` if the file does not exist, `ValueError` if any line
    cannot be parsed (the error names the line number).
    """
    proxies: list[Proxy] = []
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            try:
                proxies.append(parse_proxy_string(line))
            except ValueError as e:
                raise ValueError(f"{path}:{lineno}: {e}") from e
    return proxies


@dataclass
class _ProxyHealth:
    consecutive_failures: int = 0
    disabled_until: float = 0.0  # epoch seconds; 0 = available

    def available(self, now: float) -> bool:
        return now >= self.disabled_until


class ProxyPool:
    """Thread-safe pool of proxies with rotation and health tracking.

    Strategies:
        round_robin: cycle through proxies in insertion order
        random:      pick a uniform-random healthy proxy each time
        sticky:      keep returning the current proxy until it is marked bad

    Health model: each proxy has a consecutive-failure counter. When the
    counter reaches `max_failures` the proxy is placed on cooldown for
    `cooldown_sec` seconds. A successful call resets the counter to zero.
    """

    def __init__(
        self,
        proxies: Iterable[Proxy],
        strategy: str = "round_robin",
        max_failures: int = 3,
        cooldown_sec: float = 300.0,
        rng: Optional[random.Random] = None,
    ):
        self._proxies: list[Proxy] = list(proxies)
        if not self._proxies:
            raise ValueError("ProxyPool requires at least one proxy")
        if strategy not in ROTATION_STRATEGIES:
            raise ValueError(
                f"unknown rotation strategy '{strategy}' — use one of {ROTATION_STRATEGIES}"
            )
        self.strategy = strategy
        self.max_failures = max(1, int(max_failures))
        self.cooldown_sec = max(0.0, float(cooldown_sec))
        self._rng = rng or random.Random()
        self._health: dict[str, _ProxyHealth] = {
            p.server + (p.username or ""): _ProxyHealth() for p in self._proxies
        }
        self._lock = threading.Lock()
        self._idx = 0
        self._current: Optional[Proxy] = None
        # Patch `time.monotonic` in tests via a class attribute override
        self._now = time.monotonic

    @classmethod
    def from_strings(
        cls,
        strings: Iterable[str],
        strategy: str = "round_robin",
        **kwargs,
    ) -> "ProxyPool":
        proxies = [parse_proxy_string(s) for s in strings if s and s.strip()]
        return cls(proxies, strategy=strategy, **kwargs)

    def _key(self, p: Proxy) -> str:
        return p.server + (p.username or "")

    def __len__(self) -> int:
        return len(self._proxies)

    @property
    def size(self) -> int:
        return len(self._proxies)

    def healthy(self) -> list[Proxy]:
        """Return proxies whose cooldown has expired."""
        now = self._now()
        with self._lock:
            return [p for p in self._proxies if self._health[self._key(p)].available(now)]

    def next(self) -> Proxy:
        """Return the next proxy according to the configured strategy.

        If every proxy is in cooldown, the one with the earliest cooldown
        expiry is returned anyway (better to try a recently-failed proxy than
        to block the pipeline).
        """
        with self._lock:
            now = self._now()
            available = [p for p in self._proxies if self._health[self._key(p)].available(now)]
            pool = available or self._proxies

            if self.strategy == "random":
                self._current = self._rng.choice(pool)
            elif self.strategy == "sticky":
                if self._current is None or self._current not in pool:
                    self._current = pool[self._idx % len(pool)]
                    self._idx += 1
            else:  # round_robin
                self._current = pool[self._idx % len(pool)]
                self._idx += 1

            return self._current

    def mark_bad(self, proxy: Proxy, reason: str = "") -> None:
        """Record a failure against `proxy`; cooldown on repeated failures."""
        with self._lock:
            h = self._health.get(self._key(proxy))
            if h is None:
                return
            h.consecutive_failures += 1
            if h.consecutive_failures >= self.max_failures:
                h.disabled_until = self._now() + self.cooldown_sec
            # Sticky strategy: force rotation on next .next()
            if self.strategy == "sticky" and self._current == proxy:
                self._current = None

    def mark_good(self, proxy: Proxy) -> None:
        """Clear failure state after a successful call."""
        with self._lock:
            h = self._health.get(self._key(proxy))
            if h is None:
                return
            h.consecutive_failures = 0
            h.disabled_until = 0.0

    def status(self) -> list[dict]:
        """Snapshot of pool health — useful for debugging."""
        now = self._now()
        with self._lock:
            return [
                {
                    "proxy": str(p),
                    "failures": self._health[self._key(p)].consecutive_failures,
                    "cooldown_remaining": max(
                        0.0, self._health[self._key(p)].disabled_until - now
                    ),
                }
                for p in self._proxies
            ]
