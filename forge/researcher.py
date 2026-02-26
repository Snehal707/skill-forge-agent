"""Researcher module for Skill Forge.

Performs web research and document scraping for a given domain using the
Firecrawl Python SDK, returning a structured ResearchBundle.

Strategy
--------
1. Search for the top N URLs related to the domain.
2. Fully scrape up to `max_scrape` of those URLs (truncated to 4000 chars each).
3. If an official docs site is detected among results, crawl up to
   `max_crawl_pages` pages from it for deeper coverage.
4. Fall back to search snippets for any URL that cannot be scraped.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, List, Optional

from firecrawl import FirecrawlApp
from loguru import logger


# Patterns that identify official documentation sites worth crawling.
_DOCS_URL_PATTERNS = [
    r"docs\.",
    r"/docs/",
    r"documentation\.",
    r"readthedocs\.io",
    r"\.dev/docs",
    r"learn\.",
    r"guide\.",
]

_DOCS_PATTERN = re.compile("|".join(_DOCS_URL_PATTERNS), re.IGNORECASE)


@dataclass
class ResearchBundle:
    """Container for raw research artifacts about a domain."""

    domain: str
    sources: List[str]
    notes: str


def _get_firecrawl_app() -> FirecrawlApp:
    """Instantiate a FirecrawlApp using the FIRECRAWL_API_KEY environment variable."""
    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        raise RuntimeError("FIRECRAWL_API_KEY environment variable is required for research.")
    return FirecrawlApp(api_key=api_key)


def _scrape_url(app: FirecrawlApp, url: str, char_limit: int = 4000) -> str:
    """Scrape a single URL and return its markdown content, or empty string on failure."""
    try:
        result = app.scrape(url)
        if hasattr(result, "markdown") and result.markdown:
            return result.markdown[:char_limit]
        if isinstance(result, dict):
            md = result.get("markdown") or result.get("content") or ""
            return str(md)[:char_limit]
    except Exception:
        logger.warning("Failed to scrape URL: {url}", url=url)
    return ""


def _crawl_docs_site(
    app: FirecrawlApp,
    base_url: str,
    max_pages: int = 5,
    char_limit: int = 2000,
) -> List[str]:
    """Crawl an official docs site and return a list of markdown snippets."""
    logger.info("Crawling docs site: {url} (max {n} pages)", url=base_url, n=max_pages)
    blocks: List[str] = []
    try:
        raw = app.crawl(
            base_url,
            limit=max_pages,
            scrape_options={"formats": ["markdown"]},
        )
        # crawl() returns a CrawlStatusResponse with a .data list of Documents
        pages: List[Any] = []
        if hasattr(raw, "data") and isinstance(raw.data, list):
            pages = raw.data
        elif isinstance(raw, dict):
            pages = raw.get("data", [])
        elif isinstance(raw, list):
            pages = raw

        for page in pages[:max_pages]:
            url = ""
            content = ""
            if hasattr(page, "metadata") and page.metadata:
                url = getattr(page.metadata, "url", "") or getattr(page.metadata, "sourceURL", "") or ""
            if hasattr(page, "markdown") and page.markdown:
                content = page.markdown[:char_limit]
            elif isinstance(page, dict):
                url = page.get("metadata", {}).get("url", "") or page.get("url", "")
                content = (page.get("markdown") or page.get("content") or "")[:char_limit]

            if content:
                header = f"## Crawled page: {url}" if url else "## Crawled page"
                blocks.append(f"{header}\n\n{content}")

        logger.info("Crawled {n} pages from {url}", n=len(blocks), url=base_url)
    except Exception:
        logger.warning("Failed to crawl docs site: {url}", url=base_url)
    return blocks


def _find_docs_url(sources: List[str]) -> Optional[str]:
    """Return the best docs URL from sources, or derive one from the official domain."""
    # Prefer an explicit docs URL first.
    for url in sources:
        if _DOCS_PATTERN.search(url):
            return url

    # Fall back: for the first non-Wikipedia/GitHub source, try appending /docs/
    skip_domains = ("wikipedia.org", "github.com", "youtube.com", "reddit.com", "linkedin.com")
    for url in sources:
        if any(d in url for d in skip_domains):
            continue
        # Try <scheme>://<host>/docs/ as the docs entry point.
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if parsed.scheme and parsed.netloc:
            derived = f"{parsed.scheme}://{parsed.netloc}/docs/"
            return derived

    return None


def research_domain(
    domain: str,
    max_results: int = 5,
    max_scrape: int = 3,
    max_crawl_pages: int = 5,
) -> ResearchBundle:
    """Research a domain using Firecrawl search + full-page scraping + doc crawling.

    Parameters
    ----------
    domain:
        The target domain or topic, e.g. "docker", "kubernetes".
    max_results:
        Maximum number of search results to collect URLs from.
    max_scrape:
        How many of the top URLs to fully scrape (others use search snippets).
    max_crawl_pages:
        If an official docs site is found, crawl up to this many pages.
    """
    logger.info("Starting Firecrawl research for domain: {domain}", domain=domain)

    try:
        app = _get_firecrawl_app()
        raw: Any = app.search(domain)
    except Exception:
        logger.exception("Firecrawl search failed for domain: {domain}", domain=domain)
        raise

    sources: List[str] = []
    notes_blocks: List[str] = []

    # Normalise across all Firecrawl SDK response shapes.
    web_results: List[Any] = []
    if hasattr(raw, "web") and isinstance(raw.web, list):
        web_results = raw.web[:max_results]
    elif isinstance(raw, dict):
        data = raw.get("data") or raw.get("results") or []
        if isinstance(data, list):
            web_results = data[:max_results]
    elif isinstance(raw, list):
        web_results = raw[:max_results]

    for idx, item in enumerate(web_results):
        if hasattr(item, "url"):
            url = item.url or ""
            snippet = getattr(item, "description", "") or ""
            title = getattr(item, "title", "") or ""
        elif isinstance(item, dict):
            url = item.get("url") or item.get("sourceUrl") or ""
            snippet = (
                item.get("markdown")
                or item.get("content")
                or item.get("text")
                or item.get("description")
                or ""
            )
            title = item.get("title", "")
        else:
            continue

        if url and url not in sources:
            sources.append(str(url))

        # Fully scrape the first `max_scrape` results for rich content.
        if idx < max_scrape and url:
            logger.info("Scraping full page ({i}/{n}): {url}", i=idx + 1, n=max_scrape, url=url)
            full_content = _scrape_url(app, url)
            content = full_content if full_content else snippet
        else:
            content = snippet

        if content:
            header = f"# {title}\n{url}" if title else f"# Source: {url}"
            notes_blocks.append(f"{header}\n\n{content}")

    # Deep crawl the official docs site if one was found in results.
    docs_url = _find_docs_url(sources)
    if docs_url:
        crawled = _crawl_docs_site(app, docs_url, max_pages=max_crawl_pages)
        notes_blocks.extend(crawled)
        logger.info(
            "Added {n} crawled doc pages for domain: {domain}", n=len(crawled), domain=domain
        )

    if not web_results:
        notes_blocks.append(str(raw))

    combined_notes = "\n\n---\n\n".join(notes_blocks) if notes_blocks else ""

    bundle = ResearchBundle(domain=domain, sources=sources, notes=combined_notes)
    logger.info(
        "Completed research for domain: {domain} — {s} sources, {p} scraped, docs crawled: {d}",
        domain=domain,
        s=len(sources),
        p=min(max_scrape, len(sources)),
        d=bool(docs_url),
    )
    return bundle
