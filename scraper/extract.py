from __future__ import annotations

import json
import re
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .types import Product


PRICE_RE = re.compile(r"(?<!\d)(\d{1,3}([\s\u00A0\.,]\d{3})*|\d+)([\.,]\d{2})?")


def _text(el) -> str:
    return (el.get_text(separator=" ", strip=True) if el else "").strip()


def _normalize_price_to_string(text: str) -> Optional[str]:
    if not text:
        return None
    m = PRICE_RE.search(text.replace("\u00A0", " "))
    if not m:
        return None
    price = m.group(0)
    # Normalize separators: keep comma for decimal if present, remove thousands
    price = price.replace("\u00A0", " ")
    price = price.replace(" ", "")
    # Handle 1.234,56 or 1,234.56 -> unify to dot decimal
    if "," in price and "." in price:
        if price.rfind(",") > price.rfind("."):
            price = price.replace(".", "").replace(",", ".")
        else:
            price = price.replace(",", "")
    else:
        # If only comma, use dot
        if "," in price and price.count(",") == 1:
            price = price.replace(",", ".")
        # If only dots as thousands, remove
        elif price.count(".") > 1:
            price = price.replace(".", "")
    return price


def _from_jsonld(soup: BeautifulSoup, base_url: str) -> Optional[Product]:
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "{}")
        except Exception:
            continue
        objects = data if isinstance(data, list) else [data]
        for obj in objects:
            if not isinstance(obj, dict):
                continue
            if obj.get("@type") == "Product":
                name = obj.get("name") or ""
                description = obj.get("description")
                image = obj.get("image")
                if isinstance(image, list):
                    image = image[0] if image else None
                offers = obj.get("offers") or {}
                price = None
                if isinstance(offers, dict):
                    price = offers.get("price") or offers.get("lowPrice") or offers.get("highPrice")
                if not price:
                    price = _normalize_price_to_string(str(obj.get("price") or ""))
                url = obj.get("url") or obj.get("@id") or base_url
                if url:
                    url = urljoin(base_url, url)
                return Product(
                    name=name.strip(),
                    price=(str(price).strip() if price else None),
                    url=url or base_url,
                    image_url=(str(image).strip() if image else None),
                    description=(str(description).strip() if description else None),
                )
    return None


def _from_opengraph(soup: BeautifulSoup, base_url: str) -> Optional[Product]:
    og = {m.get("property"): m.get("content") for m in soup.find_all("meta", property=True)}
    name = og.get("og:title")
    description = og.get("og:description")
    image = og.get("og:image")
    price = og.get("product:price:amount") or og.get("og:price:amount")

    if name or price:
        if not price:
            # try meta itemprop price
            meta_price = soup.find("meta", attrs={"itemprop": "price"})
            if meta_price and meta_price.get("content"):
                price = meta_price.get("content")
        if not price:
            price_text_el = soup.select_one("[class*='price'], [id*='price']")
            price = _normalize_price_to_string(_text(price_text_el))

        return Product(
            name=(name or "").strip() or "",
            price=(str(price).strip() if price else None),
            url=base_url,
            image_url=(image.strip() if image else None),
            description=(description.strip() if description else None),
        )
    return None


def _from_heuristics(soup: BeautifulSoup, base_url: str) -> Optional[Product]:
    # Name candidates
    name_el = (
        soup.find("h1")
        or soup.select_one("h1[class*='product'], h1[class*='title']")
        or soup.select_one(".product-title, .item-title, [itemprop='name']")
    )
    name = _text(name_el)

    # Price candidates
    price_el = (
        soup.select_one("[itemprop='price']")
        or soup.select_one(".price, .product-price, .card-price, .price__current, [class*='price']")
        or soup.find(string=PRICE_RE)
    )
    price_text = _text(price_el) if hasattr(price_el, "get_text") else str(price_el or "")
    price = _normalize_price_to_string(price_text)

    # Image candidates
    image_el = (
        soup.select_one("[itemprop='image']")
        or soup.select_one("img.product, img[class*='product'], img[class*='main']")
        or soup.find("img")
    )
    image_url = image_el.get("src") if getattr(image_el, "get", None) else None
    if image_url:
        image_url = urljoin(base_url, image_url)

    # Description candidates
    desc_el = soup.select_one("[itemprop='description'], .product-description, .description")
    description = _text(desc_el) if desc_el else None

    if name or price:
        return Product(
            name=name,
            price=price,
            url=base_url,
            image_url=image_url,
            description=description,
        )
    return None


def extract_product(url: str, html: str) -> Optional[Product]:
    soup = BeautifulSoup(html, "lxml")
    return (
        _from_jsonld(soup, url)
        or _from_opengraph(soup, url)
        or _from_heuristics(soup, url)
    )

