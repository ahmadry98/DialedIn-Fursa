"""Collect web evidence for unknown espresso gear profile drafts."""

from __future__ import annotations

import html
import io
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from typing import Any

from services.espresso_mcp import profile_source_discovery

SEARCH_URL = "https://duckduckgo.com/html/"
DEFAULT_TIMEOUT_SECONDS = 5
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
KNOWN_BRAND_DOMAINS = {
    "illy": ["illy.com"],
    "x1 anniversary": ["illy.com"],
    "x1 anniversary ese": ["illy.com"],
    "breville": ["breville.com"],
    "gaggia": ["gaggia.com"],
    "rancilio": ["ranciliogroup.com", "ranciliogroupna.com"],
    "lelit": ["lelit.com"],
    "la marzocco": ["lamarzocco.com", "home.lamarzoccousa.com"],
    "delonghi": ["delonghi.com"],
    "de longhi": ["delonghi.com"],
    "profitec": ["profitec-espresso.com"],
    "ecm": ["ecm.de"],
    "rocket": ["rocket-espresso.com"],
    "quick mill": ["quick-mill.com"],
    "quickmill": ["quick-mill.com"],
    "fellow": ["fellowproducts.com", "help.fellowproducts.com"],
    "varia": ["variabrewing.com"],
    "baratza": ["baratza.com"],
    "eureka": ["eureka.co.it"],
    "niche": ["nichecoffee.co.uk"],
}


def collect_web_evidence(
    candidate: dict[str, Any],
    *,
    max_results: int = 6,
    max_chars_per_page: int = 2600,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    source_discovery: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Search the web and fetch a compact evidence packet for one candidate."""
    name = str(candidate.get("name_entered", "")).strip()
    gear_type = str(candidate.get("type", "")).strip()
    if not name or gear_type not in {"machine", "grinder"}:
        return {"sources": [], "text": ""}

    found: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    source_discovery = source_discovery or {}
    search_result_count = 0
    for query in unique([*build_discovery_queries(gear_type, name, source_discovery), *build_queries(gear_type, name)]):
        for result in search_web(query, timeout=timeout):
            before_count = len(found)
            _append_result(found, seen_urls, result, query)
            if len(found) > before_count:
                search_result_count += 1
            if search_result_count >= max_results * 4:
                break
        if search_result_count >= max_results * 5:
            break

    for result in [*build_discovered_url_candidates(source_discovery), *build_direct_url_candidates(gear_type, name)]:
        _append_result(found, seen_urls, result, result.get("query", "direct official URL fallback"))

    ranked = sorted(found, key=lambda item: score_result(item, gear_type, name), reverse=True)[: max_results * 18]
    sources: list[dict[str, str]] = []
    evidence_chunks: list[str] = []
    seen_families: set[str] = set()
    fetch_attempts = 0
    max_fetch_attempts = max_results * 3
    for result in ranked:
        if fetch_attempts >= max_fetch_attempts:
            break
        family = source_family_key(result["url"])
        if family in seen_families:
            continue
        fetch_attempts += 1
        page_text = fetch_page_text(result["url"], timeout=timeout, max_chars=max_chars_per_page)
        if not page_text and result.get("source") == "direct_fallback":
            continue
        if not page_text and not result.get("snippet"):
            continue
        seen_families.add(family)
        source = {
            "url": result["url"],
            "title": result.get("title", ""),
            "snippet": result.get("snippet", ""),
            "query": result.get("query", ""),
            "source_type": source_type(result["url"]),
        }
        sources.append(source)
        evidence_chunks.append(format_evidence_chunk(source, page_text))
        if len(sources) >= max_results:
            break

    return {"sources": sources, "text": "\n\n".join(chunk for chunk in evidence_chunks if chunk.strip())}


def build_discovery_queries(gear_type: str, name: str, source_discovery: dict[str, Any] | None) -> list[str]:
    """Build focused searches from source-discovery hints."""
    if not source_discovery:
        return []

    queries: list[str] = [str(query) for query in source_discovery.get("search_queries", []) if str(query).strip()]
    quoted = f'"{name}"'
    for domain in profile_source_discovery.discovery_domains(source_discovery):
        if gear_type == "machine":
            queries.extend(
                [
                    f"site:{domain} {quoted} official specifications manual",
                    f"site:{domain} {quoted} portafilter pump preinfusion technical",
                ]
            )
        else:
            queries.extend(
                [
                    f"site:{domain} {quoted} grinder official specifications",
                    f"site:{domain} {quoted} espresso range adjustment manual",
                ]
            )
    return unique(queries)


def build_discovered_url_candidates(source_discovery: dict[str, Any] | None) -> list[dict[str, str]]:
    """Convert discovered exact URLs into fetchable evidence candidates."""
    if not source_discovery:
        return []

    results: list[dict[str, str]] = []
    for url in profile_source_discovery.discovery_urls(source_discovery):
        results.append(
            {
                "url": url,
                "title": "Source discovery candidate",
                "snippet": "Likely official source URL suggested by source discovery and fetched for confirmation.",
                "source": "source_discovery_url",
                "query": "source discovery exact URL",
            }
        )
    return results


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
    brand_domains = brand_domain_candidates(name, tokens)
    slug_variants = slug_candidates(tokens)
    if gear_type == "machine":
        slugs = unique([*slug_variants, *machine_specific_slug_candidates(tokens), *(f"{slug}-espresso-machine" for slug in slug_variants), "espresso-machine"])
    else:
        slugs = unique([*slug_variants, *(f"{slug}-grinder" for slug in slug_variants), "espresso-grinder", "coffee-grinder"])

    domains = []
    for domain in known_brand_domains(name):
        domains.extend([f"https://www.{domain}", f"https://{domain}"])
    for brand in brand_domains:
        domains.extend(
            [
                f"https://www.{brand}.com",
                f"https://{brand}.com",
            ]
        )
    domains = unique(domains)
    paths = [
        "/en/products/domestic-machines/{slug}",
        "/en/products/coffee-grinders/{slug}",
        "/en-ca/products/{slug}",
        "/en-eu/products/{slug}",
        "/products/{slug}",
        "/products/{slug}/",
        "/product/{slug}",
        "/product/{slug}/",
        "/manuals/{slug}",
        "/en/technical-documentation",
        "/it/documentazione-tecnica",
    ]
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
    results.extend(known_direct_asset_candidates(name))
    return results


def known_direct_asset_candidates(name: str) -> list[dict[str, str]]:
    normalized = " ".join(re.split(r"[^a-z0-9]+", name.lower())).strip()
    results: list[dict[str, str]] = []
    if "lelit" in normalized and "elizabeth" in normalized:
        results.append(
            {
                "url": "https://assets.breville.com/Lelit/PESEL01/LELIT-Elizabeth-PL92T-120-EN.pdf",
                "title": "Official LELIT Elizabeth PL92T technical manual PDF",
                "snippet": "Official technical manual PDF candidate for LELIT Elizabeth PL92T.",
                "source": "direct_asset",
            }
        )
    if "quick mill" in normalized and "silvano" in normalized:
        results.append(
            {
                "url": "https://www.quick-mill.com/products/silvano/",
                "title": "Official Quick Mill Silvano product page",
                "snippet": "Official Quick Mill Silvano page with technical characteristics.",
                "source": "direct_asset",
            }
        )
    if "fellow" in normalized and "opus" in normalized and "opus 2" not in normalized:
        results.extend(
            [
                {
                    "url": "https://fellowproducts.com/collections/gifts-under-250/products/opus-coffee-grinder",
                    "title": "Official Fellow Opus Conical Burr Grinder product page",
                    "snippet": "Official Fellow Opus product page with burr size and grind settings.",
                    "source": "direct_asset",
                },
                {
                    "url": "https://help.fellowproducts.com/hc/en-us/articles/12697812844315-What-does-the-Opus-inner-adjustment-ring-do-and-how-do-I-use-it",
                    "title": "Official Fellow Opus inner adjustment support article",
                    "snippet": "Official Fellow support page explaining Opus grind adjustment rings and minor increments.",
                    "source": "direct_asset",
                },
                {
                    "url": "https://help.fellowproducts.com/hc/en-us/articles/12697501813403-What-are-the-differences-between-Opus-and-Ode",
                    "title": "Official Fellow Opus and Ode comparison support article",
                    "snippet": "Official Fellow support page with Opus settings, burrs, and espresso suitability.",
                    "source": "direct_asset",
                },
            ]
        )
    return results


def machine_specific_slug_candidates(tokens: list[str]) -> list[str]:
    candidates: list[str] = []
    token_set = set(tokens)
    if {"new", "casa", "bar"}.issubset(token_set) or "casabar" in token_set:
        candidates.extend(
            [
                "new-casabar",
                "new-casabar-black",
                "new-casabar-steel",
                "new-casabar-pid-black",
                "new-casabar-pid-steel",
            ]
        )
    return unique(candidates)


def known_brand_domains(name: str) -> list[str]:
    normalized = " ".join(re.split(r"[^a-z0-9]+", name.lower())).strip()
    domains: list[str] = []
    for hint, hint_domains in KNOWN_BRAND_DOMAINS.items():
        if hint in normalized:
            domains.extend(hint_domains)
    return unique(domains)


def brand_domain_candidates(name: str, tokens: list[str]) -> list[str]:
    raw_tokens = [token for token in re.split(r"[^a-z0-9]+", name.lower()) if token]
    candidates: list[str] = []
    if raw_tokens:
        if len(raw_tokens) >= 2 and raw_tokens[0] in {"la", "le", "de", "del", "deLonghi".lower()}:
            candidates.append(raw_tokens[0] + raw_tokens[1])
        candidates.append(raw_tokens[0])
    if tokens:
        candidates.append(tokens[0])
    return unique(candidates)


def slug_candidates(tokens: list[str]) -> list[str]:
    candidates = ["-".join(tokens)]
    without_brand = tokens[1:]
    if without_brand:
        candidates.append("-".join(without_brand))
    if len(tokens) >= 3:
        candidates.append("-".join([*tokens[:-2], "".join(tokens[-2:])]))
    if len(without_brand) >= 3:
        candidates.append("-".join([*without_brand[:-2], "".join(without_brand[-2:])]))
    model_tokens = [token for token in tokens if re.search(r"\d", token)]
    word_tokens = [token for token in tokens if not re.search(r"\d", token)]
    if model_tokens:
        candidates.extend(model_tokens)
        if word_tokens:
            candidates.append("-".join([word_tokens[-1], model_tokens[-1]]))
    return unique(candidates)


def unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def build_queries(gear_type: str, name: str) -> list[str]:
    quoted = f'"{name}"'
    brand_site_queries = [f"site:{domain} {quoted} official specifications manual" for domain in known_brand_domains(name)]
    asset_site_queries = [f"site:{domain} {quoted} pdf technical data manual" for domain in trusted_asset_domains(name) if domain not in known_brand_domains(name)]
    if gear_type == "machine":
        return [
            *brand_site_queries,
            *asset_site_queries,
            f"{quoted} official manufacturer technical specifications portafilter pump preinfusion boiler pressure",
            f"{quoted} official manual pdf technical data",
            f"{quoted} manufacturer support manual specifications",
            f"{quoted} spare parts filterholder group pump",
        ]
    return [
        *brand_site_queries,
        f"{quoted} grinder official manufacturer specifications espresso range clicks",
        f"{quoted} grinder official manual pdf adjustment clicks",
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


def fetch_page_text(url: str, *, timeout: int = DEFAULT_TIMEOUT_SECONDS, max_chars: int = 2600) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 DialedINProfileResearch/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get("content-type", "").lower()
            body = response.read(2_500_000)
    except Exception:
        return ""

    if url.lower().endswith(".pdf") or "application/pdf" in content_type:
        return extract_pdf_text(body, max_chars=max_chars)
    if "text/html" not in content_type and "text/plain" not in content_type:
        return ""
    return clean_page_text(body.decode("utf-8", errors="ignore"))[:max_chars]


def extract_pdf_text(pdf_bytes: bytes, *, max_chars: int = 2600) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return "PDF source found, but pypdf is not installed so text could not be extracted."

    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        chunks: list[str] = []
        for page in reader.pages[:6]:
            chunks.append(page.extract_text() or "")
            if sum(len(chunk) for chunk in chunks) >= max_chars:
                break
    except Exception:
        return ""
    return clean_page_text(" ".join(chunks))[:max_chars]


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
    if gear_type == "machine" and any(term in haystack for term in ["espresso", "portafilter", "filterholder", "preinfusion", "pump", "boiler", "technical", "manual"]):
        score += 3
    if gear_type == "grinder" and any(term in haystack for term in ["grinder", "espresso range", "click", "burr"]):
        score += 3
    url = result.get("url", "").lower()
    host = urllib.parse.urlparse(url).netloc.lower()
    official_domains = known_brand_domains(name)
    if any(host == domain or host.endswith(f".{domain}") for domain in official_domains):
        score += 18
    if "x1tech.com" in host and "illy.com" in official_domains:
        score -= 20
    if result.get("source") == "source_discovery_url":
        score += 28
    if result.get("source") == "direct_asset":
        score += 18
    if result.get("source") == "direct_fallback":
        score += 1
        has_name_token = any(token in url for token in normalized_tokens(name))
        if has_name_token and "-espresso-machine" not in url and "-grinder" not in url and "espresso-machine" not in url:
            score += 5
    if url.endswith(".pdf"):
        score += 12
    if any(term in url for term in ["manual", "technical", "spec", "asset", "download"]):
        score += 6
    if any(host == domain or host.endswith(f".{domain}") for domain in trusted_asset_domains(name)):
        score += 14
    return score


def trusted_asset_domains(name: str) -> list[str]:
    domains = known_brand_domains(name)
    normalized = " ".join(re.split(r"[^a-z0-9]+", name.lower())).strip()
    if "lelit" in normalized:
        domains.append("assets.breville.com")
    return unique(domains)


def source_type(url: str) -> str:
    parsed = urllib.parse.urlparse(url.lower())
    if parsed.path.endswith(".pdf"):
        return "pdf"
    if any(term in parsed.path for term in ["manual", "technical", "spec", "download", "asset"]):
        return "technical"
    return "web"


def source_family_key(url: str) -> str:
    parsed = urllib.parse.urlparse(url.lower())
    host = parsed.netloc.removeprefix("www.")
    path = re.sub(r"/(en|en-us|en-ca|en-eu|it|de|fr|es)(?=/)", "/{locale}", parsed.path)
    path = re.sub(r"/$", "", path)
    parts = [part for part in path.split("/") if part and part != "{locale}"]
    if host == "lelit.com" and parts:
        slug = parts[-1]
        if "manuals" in parts:
            return f"{host}/manuals/{slug}"
        if any(part in {"product", "products", "domestic-machines", "coffee-machines"} for part in parts):
            return f"{host}/products/{slug}"
    return f"{host}{path}"


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
