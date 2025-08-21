from __future__ import annotations

from typing import Iterable, List, Tuple
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


LISTING_HINT_CLASSES = (
    "product",
    "card",
    "item",
    "goods",
    "catalog",
    "grid",
)


def _same_domain(base_url: str, candidate_url: str) -> bool:
    try:
        base = urlparse(base_url)
        cand = urlparse(candidate_url)
        return base.netloc == cand.netloc or cand.netloc == ""
    except Exception:
        return False


def _dedupe_keep_order(urls: Iterable[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for u in urls:
        if u in seen:
            continue
        seen.add(u)
        result.append(u)
    return result


def _extract_jsonld_links(soup: BeautifulSoup, base_url: str) -> List[str]:
    import json

    links: List[str] = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "{}")
        except Exception:
            continue
        candidates = []
        if isinstance(data, list):
            candidates = data
        elif isinstance(data, dict):
            candidates = [data]
        for obj in candidates:
            if not isinstance(obj, dict):
                continue
            obj_type = obj.get("@type")
            if obj_type == "ItemList":
                for item in obj.get("itemListElement", []) or []:
                    if isinstance(item, dict):
                        url = item.get("url") or (item.get("item") or {}).get("@id")
                        if url:
                            links.append(urljoin(base_url, url))
            if obj_type == "Product":
                url = obj.get("url") or obj.get("@id")
                if url:
                    links.append(urljoin(base_url, url))
    return links


def discover_product_links(
    page_url: str, html: str, max_links: int = 200
) -> Tuple[bool, List[str]]:
    """
    Heuristically determine if this is a product page and/or collect product URLs from a listing page.
    Returns (is_product_page, product_links)
    """
    soup = BeautifulSoup(html, "lxml")

    # 1) JSON-LD hints
    jsonld_links = _extract_jsonld_links(soup, page_url)
    # If only Product found for current page, it's likely a product page
    is_product_page = False
    if jsonld_links:
        unique = _dedupe_keep_order(jsonld_links)
        # If the page itself is included and no other links, treat as product page
        if len(unique) == 1 and unique[0].rstrip('/') == page_url.rstrip('/'):
            is_product_page = True

    # 2) Heuristic: look for product-like containers and collect anchors
    anchors = []
    for cls in LISTING_HINT_CLASSES:
        for container in soup.select(f"div[class*='{cls}'], li[class*='{cls}'], section[class*='{cls}']"):
            anchors.extend(container.find_all("a", href=True))
    if not anchors:
        anchors = soup.find_all("a", href=True)

    candidate_urls = []
    for a in anchors:
        href = a.get("href")
        if not href or href.startswith("#"):
            continue
        abs_url = urljoin(page_url, href)
        if not _same_domain(page_url, abs_url):
            continue
        # Prefer product-ish URLs
        lower = abs_url.lower()
        if any(token in lower for token in ("/product", "/item", "/goods", "/catalog/", "sku", "id=")):
            candidate_urls.append(abs_url)

    # Merge with jsonld links
    candidate_urls.extend(jsonld_links)
    deduped = _dedupe_keep_order(candidate_urls)

    # If we have many candidate URLs, it's likely a listing page
    if len(deduped) >= 2:
        is_product_page = False

    # Cap results
    return is_product_page, deduped[:max_links]

