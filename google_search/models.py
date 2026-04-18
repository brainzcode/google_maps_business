"""Data models for Google SERP results."""

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class OrganicResult:
    """A single organic search result."""

    position: int = 0
    title: str = ""
    url: str = ""
    displayed_url: str = ""
    description: str = ""
    date: str = ""
    sitelinks: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def is_valid(self) -> bool:
        return bool(self.title.strip() and self.url.strip())

    @property
    def dedup_key(self) -> str:
        return self.url.split("?")[0].rstrip("/")


@dataclass
class AdResult:
    """A paid search result."""

    position: int = 0
    title: str = ""
    url: str = ""
    displayed_url: str = ""
    description: str = ""
    extensions: list[str] = field(default_factory=list)
    is_top: bool = True

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def is_valid(self) -> bool:
        return bool(self.title.strip())


@dataclass
class FeaturedSnippet:
    """A featured snippet / answer box."""

    title: str = ""
    url: str = ""
    content: str = ""
    content_type: str = "paragraph"  # paragraph | list | table

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def is_valid(self) -> bool:
        return bool(self.content.strip())


@dataclass
class PeopleAlsoAskItem:
    """A single People Also Ask question."""

    question: str = ""
    answer: str = ""
    url: str = ""
    title: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def is_valid(self) -> bool:
        return bool(self.question.strip())


@dataclass
class KnowledgePanelItem:
    """A knowledge panel entity card."""

    title: str = ""
    subtitle: str = ""
    description: str = ""
    entity_type: str = ""
    attributes: dict = field(default_factory=dict)
    url: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def is_valid(self) -> bool:
        return bool(self.title.strip())


@dataclass
class LocalPackResult:
    """A local pack (map 3-pack) result."""

    name: str = ""
    rating: Optional[float] = None
    reviews: Optional[int] = None
    address: str = ""
    category: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def is_valid(self) -> bool:
        return bool(self.name.strip())


@dataclass
class VideoResult:
    """A video carousel entry."""

    title: str = ""
    url: str = ""
    source: str = ""
    duration: str = ""
    date: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def is_valid(self) -> bool:
        return bool(self.title.strip() and self.url.strip())


@dataclass
class RelatedSearch:
    """A related search suggestion."""

    query: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def is_valid(self) -> bool:
        return bool(self.query.strip())


@dataclass
class SerpPage:
    """All extracted data from a single SERP page."""

    query: str = ""
    page_number: int = 0
    total_results_text: str = ""
    search_time_text: str = ""
    organic: list[OrganicResult] = field(default_factory=list)
    ads: list[AdResult] = field(default_factory=list)
    featured_snippet: Optional[FeaturedSnippet] = None
    people_also_ask: list[PeopleAlsoAskItem] = field(default_factory=list)
    knowledge_panel: Optional[KnowledgePanelItem] = None
    local_pack: list[LocalPackResult] = field(default_factory=list)
    videos: list[VideoResult] = field(default_factory=list)
    related_searches: list[RelatedSearch] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "page_number": self.page_number,
            "total_results_text": self.total_results_text,
            "search_time_text": self.search_time_text,
            "organic": [r.to_dict() for r in self.organic],
            "ads": [a.to_dict() for a in self.ads],
            "featured_snippet": self.featured_snippet.to_dict() if self.featured_snippet else None,
            "people_also_ask": [p.to_dict() for p in self.people_also_ask],
            "knowledge_panel": self.knowledge_panel.to_dict() if self.knowledge_panel else None,
            "local_pack": [lp.to_dict() for lp in self.local_pack],
            "videos": [v.to_dict() for v in self.videos],
            "related_searches": [rs.to_dict() for rs in self.related_searches],
        }


@dataclass
class SerpResultSet:
    """Collection of SERP pages across pagination for a single query."""

    pages: list[SerpPage] = field(default_factory=list)
    _seen_urls: set[str] = field(default_factory=set, repr=False)

    def add_page(self, page: SerpPage) -> None:
        """Add a page of results, deduplicating organic results by URL."""
        deduped_organic = []
        for result in page.organic:
            key = result.dedup_key
            if key not in self._seen_urls:
                self._seen_urls.add(key)
                deduped_organic.append(result)
        page.organic = deduped_organic
        self.pages.append(page)

    def all_organic(self) -> list[OrganicResult]:
        """Return all organic results across pages (already deduped)."""
        results = []
        for page in self.pages:
            results.extend(page.organic)
        return results

    def all_urls(self) -> list[str]:
        """Return all unique organic URLs."""
        return [r.url for r in self.all_organic()]

    def __len__(self) -> int:
        return sum(len(p.organic) for p in self.pages)

    def __bool__(self) -> bool:
        return len(self) > 0
