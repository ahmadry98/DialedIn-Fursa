"""Collect web evidence for unknown espresso gear profile drafts."""

from __future__ import annotations

import html
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from typing import Any

SEARCH_URL = "https://duckduckgo.com/html/"
DEFAULT_TIMEOUT_SECONDS = 8
BLOCKED_DOMAINS = {
    "amazon.",
    "ebay.",
    "facebook.",
    "instagram.",
    "reddit.",
    "tiktok.",
    "youtube.",
}
OFFICIAL_HINTS = {
    "official",
    "manufacturer",
    "manual",
    "support",
    "product",
    "spec",
    "specs",
    "pdf",
}


def collect_web_evidence(
    candidate: dict[str, Any],
    *,
    max_results: int = 4,
    max_chars_per_page: int = 1800,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Search the web and fetch a compact evidence packet for one candidate."""
    name = str(candidate.get("name_entered", "")).strip()
    gear_type = str(candidate.get("type", "")).strip()
    if not name or gear_type not in {"machine", "grinder"}:
        return {"sources": [], "text": ""}

    found: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for query in build_queries(gear_type, name):
        for result in search_web(query, timeout=timeout):
            _append_result(found, seen_urls, result, query)
            if len(found) >= max_results * 3:
                break
        if len(found) >= max_results * 3:
            break

    if len(found) < max_results:
        for result in build_direct_url_candidates(gear_type, name):
            _append_result(found, seen_urls, result, "direct official URL fallback")

    ranked = sorted(found, key=lambda item: score_result(item, gear_type, name), reverse=True)[: max_results * 8]
    sources: list[dict[str, str]] = []
    evidence_chunks: list[str] = []
    for result in ranked:
        page_text = fetch_page_text(result["url"], timeout=timeout, max_chars=max_chars_per_page)
        if not page_text and result.get("source") == "direct_fallback":
            continue
        if not page_text and not result.get("snippet"):
            continue
        source = {
            "url": result["url"],
            "title": result.get("title", ""),
            "snippet": result.get("snippet", ""),
            "query": result.get("query", ""),
        }
        sources.append(source)
        evidence_chunks.append(format_evidence_chunk(source, page_text))
        if len(sources) >= max_results:
            break

    return {"sources": sources, "text": "\n\n".join(chunk for chunk in evidence_chunks if chunk.strip())}


def _append_result(found: list[dict[str, str]], seen_urls: set[str], result: dict[str, str], query: str) -> None:
    url = normalize_url(result.get("url", ""))
    if not url or url in seen_urls or is_blocked_url(url):
        return
    seen_urls.add(url)
    item = dict(result)
    item["url"] = url
    item["query"] = query
    found.append(item)


def build_direct_url_candidates(gear_type: str, name: str) -> list[dict[str, str]]:
    tokens = normalized_tokens(name)
    if not tokens:
        return []
    brand = tokens[0]
    slug_base = "-".join(tokens)
    if gear_type == "machine":
        slugs = [f"{slug_base}-espresso-machine", "espresso-machine", slug_base]
    else:
        slugs = [f"{slug_base}-grinder", "espresso-grinder", "coffee-grinder", slug_base]

    domains = [
        f"https://www.{brand}tech.com",
        f"https://{brand}tech.com",
        f"https://eu.{brand}tech.com",
        f"https://www.{brand}.com",
        f"https://{brand}.com",
        f"https://{brand}ae.com",
    ]
    paths = ["/en-ca/products/{slug}", "/en-eu/products/{slug}", "/products/{slug}", "/product/{slug}", "/manuals/{slug}"]
    results: list[dict[str, str]] = []
    for domain in domains:
        for slug in slugs:
            for path in paths:
                results.append(
                    {
                        "url": domain + path.format(slug=slug),
                        "title": f"Possible official {name} page",
                        "snippet": "Direct official URL fallback generated from the entered gear name.",
                        "source": "direct_fallback",
                    }
                )
    return results


def build_queries(gear_type: str, name: str) -> list[str]:
    quoted = f'"{name}"'
    if gear_type == "machine":
        return [
            f"{quoted} espresso machine official specifications portafilter pump preinfusion",
            f"{quoted} espresso machine manual pdf",
            f"{quoted} manufacturer espresso machine specs",
        ]
    return [
        f"{quoted} grinder official specifications espresso range clicks",
        f"{quoted} grinder manual pdf adjustment clicks",
        f"{quoted} coffee grinder manufacturer specs",
    ]


def search_web(query: str, *, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> list[dict[str, str]]:
    params = urllib.parse.urlencode({"q": query})
    request = urllib.request.Request(
        f"{SEARCH_URL}?{params}",
        headers={"User-Agent": "Mozilla/5.0 DialedINProfileResearch/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(800_000).decode("utf-8", errors="ignore")
    except Exception:
        return []
    return DuckDuckGoResultParser.parse(body)


def fetch_page_text(url: str, *, timeout: int = DEFAULT_TIMEOUT_SECONDS, max_chars: int = 1800) -> str:
    if url.lower().endswith(".pdf"):
        return "PDF source found. Use the URL/title/snippet as evidence unless manual text is supplied separately."
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 DialedINProfileResearch/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type and "text/plain" not in content_type:
                return ""
            body = response.read(1_200_000).decode("utf-8", errors="ignore")
    except Exception:
        return ""
    return clean_page_text(body)[:max_chars]


def format_evidence_chunk(source: dict[str, str], page_text: str) -> str:
    parts = [
        f"URL: {source.get('url', '')}",
        f"Title: {source.get('title', '')}",
        f"Search snippet: {source.get('snippet', '')}",
    ]
    if page_text:
        parts.append(f"Page text excerpt: {page_text}")
    return "\n".join(parts)


def score_result(result: dict[str, str], gear_type: str, name: str) -> int:
    haystack = " ".join([result.get("url", ""), result.get("title", ""), result.get("snippet", "")]).lower()
    score = 0
    for token in normalized_tokens(name):
        if token in haystack:
            score += 2
    for hint in OFFICIAL_HINTS:
        if hint in haystack:
            score += 2
    if gear_type == "machine" and any(term in haystack for term in ["espresso", "portafilter", "preinfusion", "pump"]):
        score += 3
    if gear_type == "grinder" and any(term in haystack for term in ["grinder", "espresso range", "click", "burr"]):
        score += 3
    if result.get("url", "").lower().endswith(".pdf"):
        score += 4
    return score


def normalize_url(url: str) -> str:
    if not url:
        return ""
    parsed = urllib.parse.urlparse(html.unescape(url))
    if parsed.path == "/l/":
        query = urllib.parse.parse_qs(parsed.query)
        if query.get("uddg"):
            return query["uddg"][0]
    if parsed.scheme in {"http", "https"}:
        return urllib.parse.urlunparse(parsed._replace(fragment=""))
    return ""


def is_blocked_url(url: str) -> bool:
    host = urllib.parse.urlparse(url).netloc.lower()
    return any(blocked in host for blocked in BLOCKED_DOMAINS)


def normalized_tokens(name: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9]+", name.lower()) if len(token) > 2]


def clean_page_text(body: str) -> str:
    body = re.sub(r"(?is)<script.*?</script>", " ", body)
    body = re.sub(r"(?is)<style.*?</style>", " ", body)
    body = re.sub(r"(?is)<noscript.*?</noscript>", " ", body)
    body = re.sub(r"(?s)<[^>]+>", " ", body)
    body = html.unescape(body)
    body = re.sub(r"\s+", " ", body)
    return body.strip()


class DuckDuckGoResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._current: dict[str, str] | None = None
        self._capture: str | None = None
        self._parts: list[str] = []

    @classmethod
    def parse(cls, body: str) -> list[dict[str, str]]:
        parser = cls()
        parser.feed(body)
        return parser.results

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key: value or "" for key, value in attrs}
        classes = attrs_dict.get("class", "")
        if tag == "a" and "result__a" in classes:
            self._current = {"url": attrs_dict.get("href", ""), "title": "", "snippet": ""}
            self._capture = "title"
            self._parts = []
        elif self._current is not None and "result__snippet" in classes:
            self._capture = "snippet"
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._current is None or self._capture is None:
            return
        if self._capture == "title" and tag == "a":
            self._current["title"] = " ".join(" ".join(self._parts).split())
            self.results.append(self._current)
            self._capture = None
            self._parts = []
        elif self._capture == "snippet" and tag in {"a", "div"}:
            self._current["snippet"] = " ".join(" ".join(self._parts).split())
            self._capture = None
            self._parts = []
