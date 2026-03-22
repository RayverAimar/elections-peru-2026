#!/usr/bin/env python3
"""Unified news collection script for Peru 2026 election coverage.

Merges RSS ingestion (ingest_noticias.py) and search scraping
(scrape_candidate_news.py) into three sequential stages:

  Stage 1: RSS Feeds       — 25 direct feeds, parallel via ThreadPoolExecutor
  Stage 2: Search Scraping — candidate × site BFS crawl, parallel workers
  Stage 3: Dynamic Sites   — Playwright headless (opt-in with --dynamic)
  Phase 2: Embed + Store   — BGE-M3 embed, classify, INSERT with ON CONFLICT

Usage:
    python scripts/collect_news.py                           # 36 presidential, RSS + search
    python scripts/collect_news.py --workers 0               # Auto-detect CPU cores
    python scripts/collect_news.py --formula                  # Include VPs (108 candidates)
    python scripts/collect_news.py --formula --workers 8
    python scripts/collect_news.py --dynamic                  # Include Playwright sites
    python scripts/collect_news.py --candidates "Keiko,Forsyth"
    python scripts/collect_news.py --skip-rss
    python scripts/collect_news.py --skip-search
    python scripts/collect_news.py --dry-run
    python scripts/collect_news.py --resume
"""

import argparse
import json
import logging
import os
import random
import re
import sys
import threading
import time
import unicodedata
import urllib.robotparser
import xml.etree.ElementTree as ET
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus, urlparse

import feedparser
import psycopg
import trafilatura
from _db import DATABASE_URL
from _news_common import (
    build_party_search_terms,
    chunk_article,
    classify_article,
    make_url_hash,
    match_parties,
    normalize_text,
)
from pgvector.psycopg import register_vector
from sentence_transformers import SentenceTransformer

# ────────────────────────────── Paths ──────────────────────────────

_ROOT = Path(__file__).resolve().parent.parent
CANDIDATES_JSON = _ROOT / "data" / "candidatos_2026.json"
ALL_CANDIDATES_JSON = _ROOT / "data" / "all_candidates_2026.json"
BACKUP_JSONL = _ROOT / "data" / "news_backup.jsonl"
CHECKPOINT_PATH = _ROOT / "data" / "collect_checkpoint.json"

# ────────────────────────────── Logging ──────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("collect_news")

# ────────────────────────────── Thread-safe shared state ──────────────────────────────

_jsonl_lock = threading.Lock()
_visited_lock = threading.Lock()
_stats_lock = threading.Lock()


def append_jsonl(record: dict) -> None:
    """Thread-safe append a single JSON record to the backup JSONL file."""
    with _jsonl_lock, open(BACKUP_JSONL, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ────────────────────────────── User-Agent pool ──────────────────────────────

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 OPR/115.0.0.0",
    "Mozilla/5.0 (iPad; CPU OS 18_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Mobile/15E148 Safari/604.1",
]

# ────────────────────────────── RSS Feeds (Stage 1) ──────────────────────────────

RSS_FEEDS: dict[str, str] = {
    # Major outlets
    "El Comercio Política": "https://elcomercio.pe/arcio/rss/category/politica/",
    "El Comercio Elecciones": "https://elcomercio.pe/arcio/rss/category/elecciones/",
    "El Comercio Perú": "https://elcomercio.pe/arcio/rss/category/peru/",
    "El Comercio Economía": "https://elcomercio.pe/arcio/rss/category/economia/",
    "El Comercio Opinión": "https://elcomercio.pe/arcio/rss/category/opinion/",
    "Gestión Perú": "https://gestion.pe/arcio/rss/category/peru/",
    "Gestión Economía": "https://gestion.pe/arcio/rss/category/economia/",
    "Andina": "https://andina.pe/agencia/rss/3.xml",
    "La República": "https://larepublica.pe/rss/politica.xml",
    "La República Economía": "https://larepublica.pe/rss/economia.xml",
    "Correo": "https://diariocorreo.pe/arcio/rss/",
    "Correo Política": "https://diariocorreo.pe/arcio/rss/category/politica/",
    "Trome": "https://trome.com/arcio/rss/",
    # Broadcast / digital-first
    "RPP": "https://rpp.pe/rss",
    "Perú21": "https://peru21.pe/rss",
    "Canal N": "https://canaln.pe/feed",
    "Exitosa": "https://exitosanoticias.pe/feed/",
    # Alternative / regional
    "El Búho": "https://elbuho.pe/feed/",
    "La Mula": "https://lamula.pe/feed/",
    "Wayka": "https://wayka.pe/feed/",
    "Sudaca": "https://sudaca.pe/feed/",
    "Inforegión": "https://www.inforegion.pe/feed/",
    # Investigative
    "IDL Reporteros": "https://www.idl-reporteros.pe/feed/",
    "Convoca": "https://convoca.pe/rss.xml",
}

# ────────────────────────────── Site configuration (Stage 2 + 3) ──────────────────────────────


@dataclass
class SiteConfig:
    """Configuration for a single news site crawl target."""

    name: str
    base_url: str
    engine: str  # "static" or "dynamic"
    search_type: str  # "query_param", "tag_path", or "sitemap"
    search_url_template: str
    pagination_template: str | None
    results_per_page: int
    article_link_pattern: str  # regex for extracting article URLs from HTML
    max_pages: int
    rate_limit: float  # base seconds between requests


# Static search sites
STATIC_SITES: dict[str, SiteConfig] = {
    "elbuho": SiteConfig(
        name="El Búho",
        base_url="https://elbuho.pe",
        engine="static",
        search_type="query_param",
        search_url_template="https://elbuho.pe/?s={query}",
        pagination_template="https://elbuho.pe/page/{page}/?s={query}",
        results_per_page=10,
        article_link_pattern=r'href="(https://elbuho\.pe/\d{4}/\d{2}/[^"]+)"',
        max_pages=3,
        rate_limit=2.0,
    ),
    "wayka": SiteConfig(
        name="Wayka",
        base_url="https://wayka.pe",
        engine="static",
        search_type="query_param",
        search_url_template="https://wayka.pe/?s={query}",
        pagination_template="https://wayka.pe/page/{page}/?s={query}",
        results_per_page=10,
        article_link_pattern=r'href="(https://wayka\.pe/[^"]+)"',
        max_pages=3,
        rate_limit=2.0,
    ),
    "sudaca": SiteConfig(
        name="Sudaca",
        base_url="https://sudaca.pe",
        engine="static",
        search_type="query_param",
        search_url_template="https://sudaca.pe/?s={query}",
        pagination_template="https://sudaca.pe/page/{page}/?s={query}",
        results_per_page=9,
        article_link_pattern=r'href="(https://sudaca\.pe/[^"]+)"',
        max_pages=3,
        rate_limit=2.0,
    ),
    "gestion": SiteConfig(
        name="Gestión",
        base_url="https://gestion.pe",
        engine="static",
        search_type="tag_path",
        search_url_template="https://gestion.pe/noticias/{tag}/",
        pagination_template="https://gestion.pe/noticias/{tag}/{offset}/",
        results_per_page=20,
        article_link_pattern=r'href="(https://gestion\.pe/[^"]+noticia[^"]*)"',
        max_pages=3,
        rate_limit=2.5,
    ),
    "correo": SiteConfig(
        name="Correo",
        base_url="https://diariocorreo.pe",
        engine="static",
        search_type="tag_path",
        search_url_template="https://diariocorreo.pe/noticias/{tag}/",
        pagination_template="https://diariocorreo.pe/noticias/{tag}/{offset}/",
        results_per_page=20,
        article_link_pattern=r'href="(https://diariocorreo\.pe/[^"]+noticia[^"]*)"',
        max_pages=3,
        rate_limit=2.5,
    ),
    "larepublica": SiteConfig(
        name="La República",
        base_url="https://larepublica.pe",
        engine="static",
        search_type="tag_path",
        search_url_template="https://larepublica.pe/tag/{tag}",
        pagination_template=None,
        results_per_page=50,
        article_link_pattern=r'href="(https://larepublica\.pe/[^"]+\d{4}/\d{2}/\d{2}/[^"]+)"',
        max_pages=1,
        rate_limit=2.0,
    ),
    "elcomercio_sitemap": SiteConfig(
        name="El Comercio",
        base_url="https://elcomercio.pe",
        engine="static",
        search_type="sitemap",
        search_url_template="https://elcomercio.pe/sitemap/news/politica/?outputType=xml",
        pagination_template=None,
        results_per_page=0,
        article_link_pattern=r"<loc>(https://elcomercio\.pe/[^<]+)</loc>",
        max_pages=1,
        rate_limit=2.0,
    ),
    "idl_sitemap": SiteConfig(
        name="IDL Reporteros",
        base_url="https://www.idl-reporteros.pe",
        engine="static",
        search_type="sitemap",
        search_url_template="https://www.idl-reporteros.pe/wp-sitemap-posts-post-1.xml",
        pagination_template=None,
        results_per_page=0,
        article_link_pattern=r"<loc>(https://www\.idl-reporteros\.pe/[^<]+)</loc>",
        max_pages=1,
        rate_limit=2.0,
    ),
}

# Dynamic sites (require Playwright) — used in Stage 3
DYNAMIC_SITES: dict[str, SiteConfig] = {
    "rpp": SiteConfig(
        name="RPP",
        base_url="https://rpp.pe",
        engine="dynamic",
        search_type="query_param",
        search_url_template="https://rpp.pe/buscar?q={query}",
        pagination_template=None,
        results_per_page=20,
        article_link_pattern=r'href="(https://rpp\.pe/[^"]+)"',
        max_pages=1,
        rate_limit=3.0,
    ),
    "canaln": SiteConfig(
        name="Canal N",
        base_url="https://canaln.pe",
        engine="dynamic",
        search_type="query_param",
        search_url_template="https://canaln.pe/buscar?q={query}",
        pagination_template=None,
        results_per_page=20,
        article_link_pattern=r'href="(https://canaln\.pe/[^"]+)"',
        max_pages=1,
        rate_limit=3.0,
    ),
}

# ────────────────────────────── URL filtering ──────────────────────────────

NON_ARTICLE_PATTERNS = re.compile(
    r"(/category/|/categories/|/tag/|/tags/|/autor/|/author/|"
    r"/search|/buscar|\?s=|\?q=|/page/\d+|/feed/?$|/rss/?$|"
    r"#comment|/wp-login|/wp-admin|/contact|/about|/acerca|/publicidad|"
    r"/suscripcion|/newsletter|/podcast|/videos?/?$|/fotos?/?$)",
    re.IGNORECASE,
)

# ────────────────────────────── Task dataclass ──────────────────────────────


@dataclass
class CrawlTask:
    """A single unit of work for the BFS search crawler."""

    url: str
    depth: int
    task_type: str  # "search" or "article"
    site_key: str
    candidate_name: str
    party_name: str


# ────────────────────────────── URL helpers ──────────────────────────────


def slugify(text: str) -> str:
    """Convert a name to a URL-friendly slug.

    Example: "Keiko Fujimori" -> "keiko-fujimori"
             "César Acuña"    -> "cesar-acuna"
    """
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in nfkd if not unicodedata.combining(c))
    slug = re.sub(r"[^a-z0-9-]", "", ascii_text.lower().replace(" ", "-").replace("_", "-"))
    return re.sub(r"-+", "-", slug).strip("-")


def get_search_url(config: SiteConfig, candidate_name: str) -> str:
    """Build the primary search/listing URL for a candidate on a given site."""
    if config.search_type == "query_param":
        query = quote_plus(candidate_name)
        return config.search_url_template.format(query=query)
    elif config.search_type == "tag_path":
        tag = slugify(candidate_name)
        return config.search_url_template.format(tag=tag)
    elif config.search_type == "sitemap":
        return config.search_url_template
    else:
        raise ValueError(f"Unknown search_type: {config.search_type!r}")


def get_pagination_urls(config: SiteConfig, candidate_name: str, max_pages: int) -> list[str]:
    """Build pagination URLs for pages 2..max_pages."""
    if not config.pagination_template or max_pages <= 1:
        return []

    urls: list[str] = []
    if config.search_type == "query_param":
        query = quote_plus(candidate_name)
        for page in range(2, max_pages + 1):
            urls.append(config.pagination_template.format(page=page, query=query))
    elif config.search_type == "tag_path":
        tag = slugify(candidate_name)
        for page in range(2, max_pages + 1):
            offset = page * config.results_per_page
            urls.append(config.pagination_template.format(tag=tag, offset=offset))
    return urls


def filter_sitemap_urls(all_urls: list[str], candidate_name: str, party_name: str) -> list[str]:
    """Filter sitemap URLs to those plausibly related to the candidate or party."""
    candidate_slug = slugify(candidate_name)
    party_slug = slugify(party_name)
    name_parts = [slugify(p) for p in candidate_name.split() if len(p) > 2]
    party_parts = [slugify(p) for p in party_name.split() if len(p) > 3]

    relevant: list[str] = []
    for url in all_urls:
        url_lower = url.lower()
        if candidate_slug in url_lower:
            relevant.append(url)
            continue
        if any(part in url_lower for part in name_parts if len(part) > 4):
            relevant.append(url)
            continue
        if party_slug in url_lower:
            relevant.append(url)
            continue
        if any(part in url_lower for part in party_parts if len(part) > 5):
            relevant.append(url)
            continue
    return relevant


def parse_sitemap_urls(xml_text: str, pattern: str) -> list[str]:
    """Extract all <loc> URLs from a sitemap XML, with regex fallback."""
    urls: list[str] = []
    try:
        root = ET.fromstring(xml_text)
        for loc_el in root.iter():
            if loc_el.tag.endswith("loc") and loc_el.text:
                urls.append(loc_el.text.strip())
        if urls:
            return urls
    except ET.ParseError:
        pass
    return re.findall(pattern, xml_text)


def _extract_title_from_url(url: str) -> str:
    """Derive a rough human-readable title from the article URL slug."""
    path = urlparse(url).path.rstrip("/")
    slug = path.split("/")[-1]
    slug = re.sub(r"^\d+-", "", slug)
    return slug.replace("-", " ").replace("_", " ").title()


# ────────────────────────────── Content extraction ──────────────────────────────


def extract_article(html: str, url: str = "") -> dict | None:
    """Extract article content + rich metadata from HTML using trafilatura.bare_extraction().

    Returns a dict with content, title, author, date, description, image, tags,
    or None if the content is too short.
    """
    try:
        data = trafilatura.bare_extraction(
            html,
            url=url or None,
            include_comments=False,
            include_tables=False,
        )
    except Exception:
        return None

    if not data or not data.get("text") or len(data.get("text", "")) < 100:
        return None

    return {
        "content": data["text"],
        "title": data.get("title") or "",
        "author": data.get("author") or "",
        "date": data.get("date") or "",
        "description": data.get("description") or "",
        "image": data.get("image") or "",
        "tags": data.get("tags") or [],
    }


def _parse_date(date_str: str) -> datetime | None:
    """Parse an ISO-style date string into a datetime, returning None on failure."""
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(date_str[:19], fmt[:len(date_str[:19])])
        except ValueError:
            continue
    return None


# ────────────────────────────── Static HTTP crawler ──────────────────────────────


class StaticCrawler:
    """Fetches pages using requests.Session with rotating user-agents and robots.txt respect."""

    def __init__(self) -> None:
        import requests
        self.session = requests.Session()
        self._robots_cache: dict[str, urllib.robotparser.RobotFileParser] = {}

    def _get_headers(self) -> dict[str, str]:
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "es-PE,es;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
        }

    def _get_robots_parser(self, base_url: str) -> urllib.robotparser.RobotFileParser:
        if base_url not in self._robots_cache:
            rp = urllib.robotparser.RobotFileParser()
            robots_url = f"{base_url.rstrip('/')}/robots.txt"
            try:
                rp.set_url(robots_url)
                rp.read()
            except Exception:
                pass
            self._robots_cache[base_url] = rp
        return self._robots_cache[base_url]

    def can_fetch(self, base_url: str, url: str) -> bool:
        rp = self._get_robots_parser(base_url)
        try:
            return rp.can_fetch("*", url)
        except Exception:
            return True

    def fetch_page(self, url: str, base_url: str, max_retries: int = 3) -> str | None:
        """Fetch a URL and return the HTML text, or None on failure.

        Handles 429 with exponential backoff. Rotates User-Agent on each retry.
        """
        import requests

        if not self.can_fetch(base_url, url):
            log.debug("robots.txt disallows: %s", url)
            return None

        for attempt in range(max_retries):
            try:
                resp = self.session.get(
                    url,
                    headers=self._get_headers(),
                    timeout=20,
                    allow_redirects=True,
                )

                if resp.status_code == 429:
                    wait = (2 ** attempt) * 5 + random.uniform(0, 2)
                    log.warning("429 on %s — backing off %.1fs", url, wait)
                    time.sleep(wait)
                    continue

                if resp.status_code == 404:
                    return None

                if resp.status_code >= 400:
                    log.debug("HTTP %d for %s", resp.status_code, url)
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)
                    continue

                return resp.text

            except requests.exceptions.Timeout:
                log.debug("Timeout fetching %s (attempt %d)", url, attempt + 1)
                time.sleep(2 ** attempt)
            except requests.exceptions.ConnectionError as e:
                log.debug("Connection error for %s: %s", url, e)
                time.sleep(2 ** attempt)
            except Exception as e:
                log.debug("Unexpected error fetching %s: %s", url, e)
                break

        return None

    def extract_article_urls(self, html: str, pattern: str, base_url: str) -> list[str]:
        """Extract article URLs from HTML using the site's regex pattern."""
        raw = re.findall(pattern, html)
        seen: set[str] = set()
        urls: list[str] = []
        base_parsed = urlparse(base_url)

        for url in raw:
            parsed = urlparse(url)
            if parsed.netloc and parsed.netloc != base_parsed.netloc:
                continue
            if NON_ARTICLE_PATTERNS.search(url):
                continue
            clean = url.split("#")[0].rstrip("/")
            if clean and clean not in seen:
                seen.add(clean)
                urls.append(clean)

        return urls

    def fetch_article_content(self, url: str, base_url: str) -> dict | None:
        """Fetch and extract article dict using bare_extraction for rich metadata."""
        html = self.fetch_page(url, base_url)
        if not html:
            return None
        return extract_article(html, url)

    def close(self) -> None:
        self.session.close()


# ────────────────────────────── Dynamic crawler (Playwright) ──────────────────────────────


class DynamicCrawler:
    """Fetches JavaScript-rendered pages using headless Chromium via Playwright.

    Playwright is imported lazily inside start() to avoid ImportError when
    the --dynamic flag is not used.
    """

    def __init__(self) -> None:
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    def start(self) -> None:
        """Launch the headless Chromium browser."""
        try:
            from playwright.sync_api import sync_playwright  # noqa: PLC0415
        except ImportError:
            log.error(
                "playwright not installed. Run: uv add playwright && playwright install chromium"
            )
            sys.exit(1)

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=True)
        self._context = self._browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            locale="es-PE",
            extra_http_headers={"Accept-Language": "es-PE,es;q=0.9", "DNT": "1"},
        )
        self._page = self._context.new_page()
        log.info("DynamicCrawler: Chromium browser started")

    def stop(self) -> None:
        """Gracefully close the browser."""
        try:
            if self._page:
                self._page.close()
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception as e:
            log.debug("DynamicCrawler.stop error: %s", e)
        log.info("DynamicCrawler: browser stopped")

    def fetch_page(self, url: str, timeout_ms: int = 30_000) -> str | None:
        """Navigate to URL, wait for networkidle, return rendered HTML."""
        if not self._page:
            raise RuntimeError("DynamicCrawler.start() must be called first")
        try:
            self._page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            return self._page.content()
        except Exception as e:
            log.debug("DynamicCrawler.fetch_page error for %s: %s", url, e)
            return None

    def fetch_article_content(self, url: str) -> dict | None:
        """Fetch rendered HTML and extract article dict with bare_extraction."""
        html = self.fetch_page(url)
        if not html:
            return None
        return extract_article(html, url)

    def extract_article_urls(self, html: str, pattern: str, base_url: str) -> list[str]:
        """Extract article URLs from rendered HTML."""
        raw = re.findall(pattern, html)
        seen: set[str] = set()
        urls: list[str] = []
        base_parsed = urlparse(base_url)

        for url in raw:
            parsed = urlparse(url)
            if parsed.netloc and parsed.netloc != base_parsed.netloc:
                continue
            if NON_ARTICLE_PATTERNS.search(url):
                continue
            clean = url.split("#")[0].rstrip("/")
            if clean and clean not in seen:
                seen.add(clean)
                urls.append(clean)

        return urls


# ────────────────────────────── Stage 1: RSS Feeds ──────────────────────────────


def _fetch_rss_feed(feed_name: str, feed_url: str) -> list[dict]:
    """Fetch and parse a single RSS feed. Returns a list of raw article dicts."""
    try:
        feed = feedparser.parse(feed_url)
    except Exception as e:
        log.warning("[RSS] Failed to parse %s: %s", feed_name, e)
        return []

    articles: list[dict] = []
    for entry in feed.entries:
        published: datetime | None = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            import contextlib

            with contextlib.suppress(Exception):
                published = datetime(*entry.published_parsed[:6])

        url = entry.get("link", "")
        if not url:
            continue

        articles.append({
            "url": url,
            "title": entry.get("title", ""),
            "description": entry.get("summary", ""),
            "author": "",
            "image_url": "",
            "published_at": published,
            "source_name": feed_name,
            "source_feed": feed_name.lower().replace(" ", "_"),
            "stage": "rss",
        })

    return articles


def run_stage1_rss(workers: int) -> list[dict]:
    """Stage 1: Fetch articles from all RSS feeds in parallel.

    Each feed is a separate task. Returns the deduplicated list of article dicts.
    """
    log.info("")
    log.info("=" * 60)
    log.info("STAGE 1: RSS Feeds (%d feeds, %d workers)", len(RSS_FEEDS), workers)
    log.info("=" * 60)

    raw: list[dict] = []
    seen_hashes: set[str] = set()

    def _worker(args: tuple[str, str]) -> tuple[str, list[dict]]:
        name, url = args
        return name, _fetch_rss_feed(name, url)

    feed_items = list(RSS_FEEDS.items())

    with ThreadPoolExecutor(max_workers=max(workers, 1)) as executor:
        futures = {executor.submit(_worker, item): item[0] for item in feed_items}
        for future in as_completed(futures):
            feed_name = futures[future]
            try:
                _, articles = future.result()
                new_count = 0
                for a in articles:
                    h = make_url_hash(a["url"])
                    if h not in seen_hashes:
                        seen_hashes.add(h)
                        a["url_hash"] = h
                        raw.append(a)
                        new_count += 1
                log.info("[RSS] %-30s -> %3d found, %3d new", feed_name, len(articles), new_count)
            except Exception as e:
                log.warning("[RSS] Error in feed %s: %s", feed_name, e)

    log.info("Stage 1 complete: %d unique articles from RSS", len(raw))
    return raw


# ────────────────────────────── Stage 2: Search Scraping ──────────────────────────────


def _crawl_candidate_static(
    candidate: dict,
    sites: dict[str, SiteConfig],
    known_hashes: set[str],
    visited_urls: set[str],
    max_articles: int,
    max_pages: int | None,
    base_delay: float | None,
) -> list[dict]:
    """BFS search crawler for a single candidate. Each call gets its own StaticCrawler.

    Returns collected raw article dicts (without content fetch — that is deferred
    to the combined dedup + fetch step to avoid re-fetching articles discovered by
    multiple candidates).
    """
    name = candidate["name"]
    party = candidate["party_name"]
    crawler = StaticCrawler()

    queue: deque[CrawlTask] = deque()
    local_visited: set[str] = set()
    collected: list[dict] = []
    article_count = 0

    # Seed queue with one search task per site
    for site_key, config in sites.items():
        search_url = get_search_url(config, name)
        queue.append(CrawlTask(
            url=search_url,
            depth=0,
            task_type="search",
            site_key=site_key,
            candidate_name=name,
            party_name=party,
        ))

    while queue and article_count < max_articles:
        task = queue.popleft()

        # Skip already-visited this session (global + local)
        with _visited_lock:
            already_global = task.url in visited_urls
        if already_global or task.url in local_visited:
            continue
        local_visited.add(task.url)

        config = sites[task.site_key]
        effective_max_pages = max_pages if max_pages is not None else config.max_pages
        effective_delay = (base_delay if base_delay is not None else config.rate_limit)
        jitter = random.uniform(-0.5, 0.5)
        delay = max(effective_delay + jitter, 0.1)

        if task.task_type == "search":
            html = crawler.fetch_page(task.url, config.base_url)
            if html:
                if config.search_type == "sitemap":
                    all_urls = parse_sitemap_urls(html, config.article_link_pattern)
                    article_urls = filter_sitemap_urls(all_urls, name, party)
                    log.debug(
                        "[%s] Sitemap: %d total, %d filtered for %s",
                        config.name, len(all_urls), len(article_urls), name,
                    )
                else:
                    article_urls = crawler.extract_article_urls(
                        html, config.article_link_pattern, config.base_url
                    )
                    log.debug(
                        "[%s] Found %d article URLs for %s",
                        config.name, len(article_urls), name,
                    )

                for article_url in article_urls:
                    url_hash = make_url_hash(article_url)
                    if url_hash in known_hashes:
                        continue
                    if article_url not in local_visited:
                        queue.append(CrawlTask(
                            url=article_url,
                            depth=task.depth + 1,
                            task_type="article",
                            site_key=task.site_key,
                            candidate_name=name,
                            party_name=party,
                        ))

                # Enqueue pagination pages (depth-0 only)
                if task.depth == 0 and config.search_type != "sitemap":
                    for pag_url in get_pagination_urls(config, name, effective_max_pages):
                        if pag_url not in local_visited:
                            queue.append(CrawlTask(
                                url=pag_url,
                                depth=1,
                                task_type="search",
                                site_key=task.site_key,
                                candidate_name=name,
                                party_name=party,
                            ))
            time.sleep(delay)

        elif task.task_type == "article":
            url_hash = make_url_hash(task.url)
            if url_hash in known_hashes:
                continue

            article_data = crawler.fetch_article_content(task.url, config.base_url)
            if article_data and len(article_data.get("content", "")) >= 100:
                # Parse date from extracted metadata
                published_at = _parse_date(article_data.get("date", ""))

                collected.append({
                    "url": task.url,
                    "url_hash": url_hash,
                    "title": article_data.get("title") or _extract_title_from_url(task.url),
                    "description": article_data.get("description", ""),
                    "content": article_data["content"],
                    "author": article_data.get("author", ""),
                    "image_url": article_data.get("image", ""),
                    "published_at": published_at,
                    "source_name": config.name,
                    "source_feed": f"scraper_{task.site_key}",
                    "candidate_name": name,
                    "party_name": party,
                    "stage": "search",
                })
                article_count += 1
                log.debug("[%s] Collected article %d for %s", config.name, article_count, name)
            else:
                log.debug("[%s] No content extracted: %s", config.name, task.url)

            time.sleep(delay)

    crawler.close()

    # Update global visited set
    with _visited_lock:
        visited_urls.update(local_visited)

    log.info("[Stage 2] Done: %3d articles for %s (%s)", len(collected), name, party)
    return collected


def run_stage2_search(
    candidates: list[dict],
    known_hashes: set[str],
    workers: int,
    max_articles: int,
    max_pages: int | None,
    base_delay: float | None,
    resume_completed: set[str],
) -> list[dict]:
    """Stage 2: Parallel search scraping across all static sites.

    Each candidate is a separate thread task. Returns collected article dicts.
    """
    log.info("")
    log.info("=" * 60)
    log.info(
        "STAGE 2: Search Scraping (%d candidates, %d static sites, %d workers)",
        len(candidates), len(STATIC_SITES), workers,
    )
    log.info("=" * 60)

    all_articles: list[dict] = []
    articles_lock = threading.Lock()
    completed_names: list[str] = list(resume_completed)
    visited_urls: set[str] = set()

    def worker(candidate: dict) -> list[dict]:
        return _crawl_candidate_static(
            candidate=candidate,
            sites=STATIC_SITES,
            known_hashes=known_hashes,
            visited_urls=visited_urls,
            max_articles=max_articles,
            max_pages=max_pages,
            base_delay=base_delay,
        )

    if workers == 1:
        for i, candidate in enumerate(candidates, 1):
            log.info("── Candidate %d/%d: %s ──", i, len(candidates), candidate["name"])
            articles = worker(candidate)
            all_articles.extend(articles)
            for a in articles:
                append_jsonl({
                    "url": a["url"],
                    "title": a.get("title", ""),
                    "source": a.get("source_name", ""),
                    "candidate": candidate["name"],
                    "party": candidate["party_name"],
                    "stage": "search",
                })
            completed_names.append(candidate["name"])
            _save_checkpoint({"completed_candidates": completed_names, "articles_collected": len(all_articles)})
            log.info("Checkpoint saved. Total so far: %d articles", len(all_articles))
    else:
        log.info("Using %d parallel workers", workers)
        futures: dict = {}
        with ThreadPoolExecutor(max_workers=workers) as executor:
            for candidate in candidates:
                future = executor.submit(worker, candidate)
                futures[future] = candidate

            for future in as_completed(futures):
                candidate = futures[future]
                try:
                    articles = future.result()
                    with articles_lock:
                        all_articles.extend(articles)
                        for a in articles:
                            append_jsonl({
                                "url": a["url"],
                                "title": a.get("title", ""),
                                "source": a.get("source_name", ""),
                                "candidate": candidate["name"],
                                "party": candidate["party_name"],
                                "stage": "search",
                            })
                        completed_names.append(candidate["name"])
                        _save_checkpoint({
                            "completed_candidates": completed_names,
                            "articles_collected": len(all_articles),
                        })
                    log.info(
                        "Completed: %s — %d articles (total so far: %d)",
                        candidate["name"], len(articles), len(all_articles),
                    )
                except Exception as e:
                    log.error("Worker failed for %s: %s", candidate["name"], e)

    log.info("Stage 2 complete: %d articles from search scraping", len(all_articles))
    return all_articles


# ────────────────────────────── Stage 3: Dynamic Sites (Playwright) ──────────────────────────────


def run_stage3_dynamic(
    candidates: list[dict],
    known_hashes: set[str],
    max_articles: int,
    max_pages: int | None,
    base_delay: float | None,
) -> list[dict]:
    """Stage 3: Sequential Playwright crawl for JS-heavy sites (RPP, Canal N).

    Runs serially because a single browser instance is shared across all candidates.
    Only executed when --dynamic is passed.
    """
    log.info("")
    log.info("=" * 60)
    log.info(
        "STAGE 3: Dynamic Sites — Playwright (%d candidates, %d dynamic sites)",
        len(candidates), len(DYNAMIC_SITES),
    )
    log.info("=" * 60)

    browser = DynamicCrawler()
    browser.start()

    all_articles: list[dict] = []
    visited_urls: set[str] = set()

    try:
        for i, candidate in enumerate(candidates, 1):
            name = candidate["name"]
            party = candidate["party_name"]
            log.info("[Stage 3] %d/%d: %s", i, len(candidates), name)
            article_count = 0

            for site_key, config in DYNAMIC_SITES.items():
                if article_count >= max_articles:
                    break

                search_url = get_search_url(config, name)
                if search_url in visited_urls:
                    continue
                visited_urls.add(search_url)

                effective_delay = base_delay if base_delay is not None else config.rate_limit

                html = browser.fetch_page(search_url)
                time.sleep(max(effective_delay + random.uniform(-0.5, 0.5), 0.1))

                if not html:
                    continue

                article_urls = browser.extract_article_urls(
                    html, config.article_link_pattern, config.base_url
                )
                log.debug("[%s] Found %d article URLs for %s", config.name, len(article_urls), name)

                for article_url in article_urls:
                    if article_count >= max_articles:
                        break

                    url_hash = make_url_hash(article_url)
                    if url_hash in known_hashes or article_url in visited_urls:
                        continue
                    visited_urls.add(article_url)

                    article_data = browser.fetch_article_content(article_url)
                    time.sleep(max(effective_delay + random.uniform(-0.5, 0.5), 0.1))

                    if article_data and len(article_data.get("content", "")) >= 100:
                        published_at = _parse_date(article_data.get("date", ""))
                        record = {
                            "url": article_url,
                            "url_hash": url_hash,
                            "title": article_data.get("title") or _extract_title_from_url(article_url),
                            "description": article_data.get("description", ""),
                            "content": article_data["content"],
                            "author": article_data.get("author", ""),
                            "image_url": article_data.get("image", ""),
                            "published_at": published_at,
                            "source_name": config.name,
                            "source_feed": f"dynamic_{site_key}",
                            "candidate_name": name,
                            "party_name": party,
                            "stage": "dynamic",
                        }
                        all_articles.append(record)
                        article_count += 1
                        append_jsonl({
                            "url": article_url,
                            "title": record["title"],
                            "source": config.name,
                            "candidate": name,
                            "party": party,
                            "stage": "dynamic",
                        })

            log.info("[Stage 3] %s: collected %d articles", name, article_count)
    finally:
        browser.stop()

    log.info("Stage 3 complete: %d articles from dynamic sites", len(all_articles))
    return all_articles


# ────────────────────────────── RSS content resolution ──────────────────────────────


def resolve_rss_content(
    articles: list[dict],
    known_hashes: set[str],
    workers: int,
) -> list[dict]:
    """Fetch full article content for RSS articles using trafilatura.

    RSS feeds only provide title/description; full text requires fetching the URL.
    Each article URL is fetched in a thread pool. Already-known URLs are skipped.
    Returns only articles that have extractable content.
    """
    # Filter out already-ingested hashes
    pending = [a for a in articles if a.get("url_hash") not in known_hashes]
    if not pending:
        log.info("[RSS resolve] All %d articles already in DB, skipping content fetch", len(articles))
        return []

    log.info("[RSS resolve] Fetching content for %d new RSS articles...", len(pending))

    resolved: list[dict] = []
    resolved_lock = threading.Lock()

    def fetch_one(article: dict) -> dict | None:
        """Fetch and enrich a single RSS article with full content."""
        try:
            downloaded = trafilatura.fetch_url(article["url"])
            if not downloaded:
                return None
            data = trafilatura.bare_extraction(
                downloaded,
                url=article["url"],
                include_comments=False,
                include_tables=False,
            )
            if not data or not data.get("text") or len(data.get("text", "")) < 100:
                return None

            # Enrich the article dict with extracted metadata
            enriched = article.copy()
            enriched["content"] = data["text"]
            # Use extracted title/author/description only if RSS didn't provide them
            if not enriched.get("title"):
                enriched["title"] = data.get("title", "")
            if not enriched.get("description"):
                enriched["description"] = data.get("description", "")
            enriched["author"] = data.get("author", "")
            enriched["image_url"] = data.get("image", "")
            # Prefer extracted date when RSS published_at is missing
            if not enriched.get("published_at") and data.get("date"):
                enriched["published_at"] = _parse_date(data["date"])
            return enriched
        except Exception as e:
            log.debug("[RSS resolve] Error fetching %s: %s", article["url"], e)
            return None

    with ThreadPoolExecutor(max_workers=max(workers, 1)) as executor:
        futures = {executor.submit(fetch_one, a): a for a in pending}
        for done, future in enumerate(as_completed(futures), 1):
            try:
                result = future.result()
                if result:
                    with resolved_lock:
                        resolved.append(result)
            except Exception as e:
                log.debug("[RSS resolve] Future error: %s", e)
            if done % 25 == 0:
                log.info("[RSS resolve] %d/%d fetched, %d with content", done, len(pending), len(resolved))

    log.info("[RSS resolve] Done: %d/%d articles with content", len(resolved), len(pending))
    return resolved


# ────────────────────────────── Deduplication ──────────────────────────────


def deduplicate_articles(article_lists: list[list[dict]]) -> list[dict]:
    """Merge multiple article lists and deduplicate by url_hash.

    Earlier lists take precedence (RSS > search > dynamic) for the same hash.
    Returns a flat, deduplicated list.
    """
    seen: set[str] = set()
    result: list[dict] = []

    for lst in article_lists:
        for article in lst:
            h = article.get("url_hash") or make_url_hash(article["url"])
            article["url_hash"] = h
            if h not in seen:
                seen.add(h)
                result.append(article)

    log.info("Deduplication: %d unique articles total", len(result))
    return result


# ────────────────────────────── Phase 2: Embed + Store ──────────────────────────────


def run_phase2_store(
    articles: list[dict],
    party_terms: dict,
    dry_run: bool,
) -> dict[str, int]:
    """Phase 2: Match parties, classify, chunk, embed with BGE-M3, and INSERT to DB.

    Loads the embedding model once. Commits per article. Thread-safe JSONL backup
    is written for each successfully stored article.

    Returns a stats dict.
    """
    stats: dict[str, int] = {
        "stored": 0,
        "skipped_duplicate": 0,
        "skipped_no_content": 0,
        "skipped_no_mentions": 0,
        "adverse": 0,
        "neutral": 0,
        "positive": 0,
        "total_chunks": 0,
    }

    if not articles:
        log.info("Phase 2: No articles to store.")
        return stats

    if dry_run:
        log.info("Phase 2: dry-run mode — skipping embed + store (%d articles)", len(articles))
        stats["stored"] = 0
        return stats

    log.info("")
    log.info("=" * 60)
    log.info("PHASE 2: Embed + Store (%d articles)", len(articles))
    log.info("=" * 60)

    log.info("Loading BGE-M3 model...")
    model = SentenceTransformer("BAAI/bge-m3")
    log.info("Model loaded. Dimensions: %d", model.get_sentence_embedding_dimension())

    conn = psycopg.connect(DATABASE_URL)
    register_vector(conn)

    # Pre-load existing hashes to skip duplicates without a round-trip per article
    existing_hashes = {r[0] for r in conn.execute("SELECT url_hash FROM news_articles").fetchall()}
    articles_to_process = [a for a in articles if a.get("url_hash") not in existing_hashes]
    log.info("After DB dedup: %d new articles to process", len(articles_to_process))

    for i, article in enumerate(articles_to_process, 1):
        title_short = (article.get("title") or "")[:55]
        log.info("  [%d/%d] %s...", i, len(articles_to_process), title_short)

        content: str = article.get("content", "")
        title: str = article.get("title", "")

        if not content or len(content) < 100:
            log.debug("  SKIP: no content for %s", article["url"])
            stats["skipped_no_content"] += 1
            continue

        # Match to parties/candidates
        mentions = match_parties(content, title, party_terms)
        if not mentions:
            log.debug("  SKIP: no candidate match for %s", article["url"])
            stats["skipped_no_mentions"] += 1
            continue

        # Classify sentiment
        sentiment, categories = classify_article(content, title)
        stats[sentiment] += 1

        # Chunk with metadata header
        chunks = chunk_article(article, content, mentions)

        # Embed in batch
        texts = [c["content"] for c in chunks]
        embeddings = model.encode(texts, batch_size=32, normalize_embeddings=True)

        # Insert article — new columns: author, image_url
        row = conn.execute(
            """
            INSERT INTO news_articles
                (url, url_hash, title, description, content, source_name,
                 source_feed, published_at, sentiment_label,
                 adverse_categories, author, image_url, total_chunks)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (url) DO NOTHING
            RETURNING id
            """,
            (
                article["url"],
                article["url_hash"],
                title,
                article.get("description", ""),
                content,
                article["source_name"],
                article["source_feed"],
                article.get("published_at"),
                sentiment,
                categories,
                article.get("author", ""),
                article.get("image_url", ""),
                len(chunks),
            ),
        ).fetchone()

        if not row:
            log.debug("  SKIP: duplicate URL in DB: %s", article["url"])
            stats["skipped_duplicate"] += 1
            continue

        article_id = row[0]

        # Insert entity mentions
        for mention in mentions:
            conn.execute(
                """
                INSERT INTO news_mentions
                    (article_id, party_name, candidate_name, is_primary)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (
                    article_id,
                    mention["party_name"],
                    mention["candidate_name"],
                    mention["is_primary"],
                ),
            )

        # Insert chunks with embeddings — includes source_url for traceability
        for chunk, embedding in zip(chunks, embeddings, strict=False):
            conn.execute(
                """
                INSERT INTO news_chunks
                    (article_id, chunk_index, content, source_url, token_count, embedding)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    article_id,
                    chunk["index"],
                    chunk["content"],
                    article["url"],
                    chunk["token_count"],
                    embedding.tolist(),
                ),
            )

        # Commit per article for durability
        conn.commit()
        stats["stored"] += 1
        stats["total_chunks"] += len(chunks)

        cat_str = f" [{', '.join(categories)}]" if categories else ""
        party_str = ", ".join(m["party_name"][:20] for m in mentions[:2])
        stage_label = article.get("stage", "?")
        log.info(
            "  -> %s%s | %d chunks | %s | [%s]",
            sentiment, cat_str, len(chunks), party_str, stage_label,
        )

        # Thread-safe JSONL backup
        append_jsonl({
            "url": article["url"],
            "title": title,
            "source": article["source_name"],
            "published_at": str(article.get("published_at", "")),
            "sentiment": sentiment,
            "categories": categories,
            "mentions": [m["party_name"] for m in mentions],
            "chunks": len(chunks),
            "stage": stage_label,
        })

    conn.close()
    return stats


# ────────────────────────────── Checkpoint helpers ──────────────────────────────


def _save_checkpoint(state: dict) -> None:
    """Write collection state to a JSON checkpoint file."""
    try:
        CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
        CHECKPOINT_PATH.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        log.warning("Failed to save checkpoint: %s", e)


def _load_checkpoint() -> dict | None:
    """Load checkpoint state, or return None if not found."""
    try:
        if CHECKPOINT_PATH.exists():
            return json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning("Failed to load checkpoint: %s", e)
    return None


# ────────────────────────────── Candidate loading ──────────────────────────────


def _make_search_name(full_name: str) -> str:
    """Build a search-friendly name: first name + last two apellidos."""
    parts = full_name.split()
    if len(parts) >= 4:
        return f"{parts[0]} {parts[-2]} {parts[-1]}"
    return full_name


def load_candidates(
    filter_names: list[str] | None = None,
    include_formula: bool = False,
) -> list[dict]:
    """Load candidates from candidatos_2026.json.

    By default loads only presidential candidates (36).
    With include_formula=True, also loads vice presidents (up to 108).
    """
    with open(CANDIDATES_JSON, encoding="utf-8") as f:
        data = json.load(f)

    candidates: list[dict] = []
    seen_names: set[str] = set()

    for party in data["parties"]:
        formula = party.get("presidential_formula", {})
        positions = ["president"]
        if include_formula:
            positions.extend(["first_vice_president", "second_vice_president"])

        for position_key in positions:
            member = formula.get(position_key, {})
            if not member or not member.get("full_name"):
                continue

            full_name: str = member["full_name"]
            search_name = _make_search_name(full_name)

            if search_name in seen_names:
                continue
            seen_names.add(search_name)

            candidates.append({
                "name": search_name,
                "full_name": full_name,
                "party_name": party["party_name"],
                "position": position_key,
            })

    if filter_names:
        normalized_filters = [normalize_text(f.strip()) for f in filter_names]
        candidates = [
            c for c in candidates
            if any(nf in normalize_text(c["full_name"]) for nf in normalized_filters)
        ]
        log.info("Filtered to %d candidates matching: %s", len(candidates), filter_names)

    log.info("Loaded %d candidates", len(candidates))
    return candidates


def load_party_terms() -> dict:
    """Load and build party search terms for entity matching."""
    with open(CANDIDATES_JSON, encoding="utf-8") as f:
        presidential_data = json.load(f)

    all_candidates_list: list[dict] | None = None
    if ALL_CANDIDATES_JSON.exists():
        with open(ALL_CANDIDATES_JSON, encoding="utf-8") as f:
            all_data = json.load(f)
        all_candidates_list = all_data.get("candidates", [])
        log.info(
            "Loaded %d candidates from all_candidates_2026.json for entity matching",
            len(all_candidates_list),
        )

    party_terms = build_party_search_terms(presidential_data, all_candidates_list)
    total_people = sum(len(p["candidates"]) for p in party_terms.values())
    log.info("Party terms built: %d parties, %d candidates total", len(party_terms), total_people)
    return party_terms


# ────────────────────────────── CLI ──────────────────────────────


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Unified news collection for Peru 2026 elections (RSS + search + dynamic)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                      # 36 presidential, RSS + search, 1 worker
  %(prog)s --workers 0                          # Auto-detect CPU cores
  %(prog)s --formula                             # Include VPs (108 candidates)
  %(prog)s --formula --workers 8
  %(prog)s --dynamic                             # Include Playwright sites (RPP, Canal N)
  %(prog)s --candidates "Keiko,Forsyth"          # Filter specific candidates
  %(prog)s --skip-rss                            # Skip Stage 1 (RSS feeds)
  %(prog)s --skip-search                         # Skip Stage 2 (search scraping)
  %(prog)s --dry-run                             # Collect but don't store
  %(prog)s --resume                              # Resume from checkpoint
""",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        metavar="N",
        help="Parallel workers for Stage 1 + 2 (0=auto-detect CPU cores, default: 1)",
    )
    parser.add_argument(
        "--formula",
        action="store_true",
        help="Include VPs (first + second vice president) in addition to presidential candidates",
    )
    parser.add_argument(
        "--dynamic",
        action="store_true",
        help="Include Stage 3: Playwright headless crawl for RPP and Canal N",
    )
    parser.add_argument(
        "--candidates",
        type=str,
        default=None,
        metavar="NAMES",
        help="Comma-separated partial candidate names to filter (e.g. 'Keiko,Forsyth')",
    )
    parser.add_argument(
        "--skip-rss",
        action="store_true",
        help="Skip Stage 1 (RSS feeds)",
    )
    parser.add_argument(
        "--skip-search",
        action="store_true",
        help="Skip Stage 2 (search scraping)",
    )
    parser.add_argument(
        "--max-articles",
        type=int,
        default=100,
        metavar="N",
        help="Max articles to collect per candidate in Stage 2/3 (default: 100)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        metavar="N",
        help="Override max pagination depth per site (default: per-site setting)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=None,
        metavar="SECS",
        help="Base delay between requests in seconds (default: per-site rate_limit)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run all collection stages but do not write to the database",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume Stage 2 from checkpoint, skipping completed candidates",
    )
    return parser.parse_args()


# ────────────────────────────── Main ──────────────────────────────


def main() -> None:
    args = parse_args()

    # ── Determine worker count ──
    num_workers = args.workers
    if num_workers == 0:
        num_workers = os.cpu_count() or 4
    log.info("Workers: %d", num_workers)

    # ── Load candidates ──
    filter_names = (
        [n.strip() for n in args.candidates.split(",")] if args.candidates else None
    )
    candidates = load_candidates(filter_names=filter_names, include_formula=args.formula)

    if not candidates:
        log.error("No candidates matched the filter. Exiting.")
        sys.exit(1)

    # ── Resume support (Stage 2 checkpoint) ──
    resume_completed: set[str] = set()
    search_candidates = candidates

    if args.resume:
        checkpoint = _load_checkpoint()
        if checkpoint:
            completed = set(checkpoint.get("completed_candidates", []))
            resume_completed = completed
            before = len(search_candidates)
            search_candidates = [c for c in candidates if c["name"] not in completed]
            log.info(
                "Resuming Stage 2: skipping %d completed, %d remaining",
                before - len(search_candidates),
                len(search_candidates),
            )
        else:
            log.info("No checkpoint found, starting fresh")

    # ── Load known DB hashes for deduplication ──
    known_hashes: set[str] = set()
    if not args.dry_run:
        try:
            conn = psycopg.connect(DATABASE_URL)
            rows = conn.execute("SELECT url_hash FROM news_articles").fetchall()
            known_hashes = {r[0] for r in rows}
            conn.close()
            log.info("Loaded %d known URL hashes from DB", len(known_hashes))
        except Exception as e:
            log.warning("Could not load known hashes from DB: %s", e)
    else:
        log.info("Dry-run mode: DB writes disabled")

    # ── Load party terms ──
    party_terms = load_party_terms()

    # ────────────── Stage 1: RSS ──────────────
    stage1_articles: list[dict] = []
    if not args.skip_rss:
        raw_rss = run_stage1_rss(workers=num_workers)
        stage1_articles = resolve_rss_content(
            articles=raw_rss,
            known_hashes=known_hashes,
            workers=num_workers,
        )
        log.info("Stage 1 yielded %d articles with content", len(stage1_articles))
    else:
        log.info("Stage 1 (RSS) skipped via --skip-rss")

    # ────────────── Stage 2: Search Scraping ──────────────
    stage2_articles: list[dict] = []
    if not args.skip_search:
        stage2_articles = run_stage2_search(
            candidates=search_candidates,
            known_hashes=known_hashes,
            workers=num_workers,
            max_articles=args.max_articles,
            max_pages=args.max_pages,
            base_delay=args.delay,
            resume_completed=resume_completed,
        )
        log.info("Stage 2 yielded %d articles from search scraping", len(stage2_articles))
    else:
        log.info("Stage 2 (search scraping) skipped via --skip-search")

    # ────────────── Stage 3: Dynamic (Playwright) ──────────────
    stage3_articles: list[dict] = []
    if args.dynamic:
        stage3_articles = run_stage3_dynamic(
            candidates=candidates,
            known_hashes=known_hashes,
            max_articles=args.max_articles,
            max_pages=args.max_pages,
            base_delay=args.delay,
        )
        log.info("Stage 3 yielded %d articles from dynamic sites", len(stage3_articles))
    else:
        log.info("Stage 3 (dynamic/Playwright) skipped (pass --dynamic to enable)")

    # ────────────── Merge + Deduplicate ──────────────
    all_articles = deduplicate_articles([stage1_articles, stage2_articles, stage3_articles])
    log.info("")
    log.info("Total unique articles across all stages: %d", len(all_articles))

    if not all_articles:
        log.info("No new articles to process. Exiting.")
        return

    # ────────────── Phase 2: Embed + Store ──────────────
    stats = run_phase2_store(
        articles=all_articles,
        party_terms=party_terms,
        dry_run=args.dry_run,
    )

    # ────────────── Summary ──────────────
    log.info("")
    log.info("=" * 60)
    log.info("COLLECTION COMPLETE")
    log.info("=" * 60)
    log.info("  Articles stored:           %d", stats["stored"])
    log.info("  Total chunks:              %d", stats["total_chunks"])
    log.info("  Adverse:                   %d", stats["adverse"])
    log.info("  Neutral:                   %d", stats["neutral"])
    log.info("  Positive:                  %d", stats["positive"])
    log.info("  Skipped (no content):      %d", stats["skipped_no_content"])
    log.info("  Skipped (no match):        %d", stats["skipped_no_mentions"])
    log.info("  Skipped (duplicate URL):   %d", stats["skipped_duplicate"])
    log.info("")
    log.info("  Stage 1 (RSS):             %d articles", len(stage1_articles))
    log.info("  Stage 2 (search):          %d articles", len(stage2_articles))
    log.info("  Stage 3 (dynamic):         %d articles", len(stage3_articles))
    log.info("  JSONL backup:              %s", BACKUP_JSONL)
    log.info("  Checkpoint:                %s", CHECKPOINT_PATH)


if __name__ == "__main__":
    main()
