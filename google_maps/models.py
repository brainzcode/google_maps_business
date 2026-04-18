"""Data models for scraped business listings."""

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Business:
    """All extractable fields from a Google Maps listing."""

    name: str = ""
    category: str = ""
    address: str = ""
    phone: str = ""
    website: str = ""
    rating: Optional[float] = None
    reviews: Optional[int] = None
    price_level: str = ""
    hours: str = ""
    plus_code: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    status: str = ""
    email: str = ""
    service_options: str = ""
    url: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def is_valid(self) -> bool:
        """A business must have at least a name to be considered valid."""
        return bool(self.name.strip())

    @property
    def dedup_key(self) -> str:
        """Stable key for deduplication — URL path or name fallback."""
        if self.url:
            return self.url.split("?")[0]
        return self.name


@dataclass
class BusinessList:
    """Deduplicated collection of businesses."""

    businesses: list[Business] = field(default_factory=list)
    _seen: set[str] = field(default_factory=set, repr=False)

    def add(self, b: Business) -> bool:
        """Add business if valid and not a duplicate. Returns True if added."""
        if not b.is_valid:
            return False
        key = b.dedup_key
        if key in self._seen:
            return False
        self._seen.add(key)
        self.businesses.append(b)
        return True

    def __len__(self) -> int:
        return len(self.businesses)

    def __bool__(self) -> bool:
        return len(self.businesses) > 0
