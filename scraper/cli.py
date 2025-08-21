from __future__ import annotations

import argparse
import sys
import time
from typing import List, Optional

from .fetch import create_session, fetch_html
from .crawler import discover_product_links
from .extract import extract_product
from .excel_writer import write_products_to_excel
from .types import Product


def scrape_to_excel(
    url: str,
    out_path: str,
    template_path: Optional[str] = None,
    limit: int = 100,
    delay: float = 0.3,
    user_agent: Optional[str] = None,
    retries: int = 5,
) -> List[Product]:
    """High-level convenience function: scrape products from URL and save into Excel.

    Returns the list of extracted products.
    """
    session = create_session(user_agent=user_agent, total_retries=retries)

    print("[1/3] Определение типа страницы и сбор ссылок…", flush=True)
    final_url, html = fetch_html(url, session=session)
    is_product_page, product_links = discover_product_links(final_url, html, max_links=limit)

    products: List[Product] = []
    if is_product_page or not product_links:
        total = 1
        print(f"Найдено: страница товара. Всего к обработке: {total}", flush=True)
        print(f"[1/{total}] Обработка: {final_url} (осталось: {total-1})", flush=True)
        product = extract_product(final_url, html)
        if product:
            products.append(product)
            print(f"[1/{total}] Успешно", flush=True)
        else:
            print(f"[1/{total}] Не удалось извлечь данные", flush=True)
    else:
        total = min(limit, len(product_links))
        print(f"Найдено ссылок на товары: {len(product_links)}. Будет обработано: {total}", flush=True)
        seen = set()
        processed = 0
        for idx_raw, link in enumerate(product_links, start=1):
            if link in seen:
                continue
            seen.add(link)
            try:
                current = processed + 1
                if current > total:
                    break
                remaining = total - current
                print(f"[{current}/{total}] Обработка: {link} (осталось: {remaining})", flush=True)
                _, p_html = fetch_html(link, session=session, pause_seconds=delay)
                product = extract_product(link, p_html)
                if product:
                    products.append(product)
                    print(f"[{current}/{total}] Успешно", flush=True)
                else:
                    print(f"[{current}/{total}] Не удалось извлечь данные", flush=True)
                processed += 1
            except Exception as exc:
                print(f"[warn] failed to fetch/extract {link}: {exc}", file=sys.stderr)

            if len(products) >= limit:
                break

    print("[2/3] Сохранение в Excel…", flush=True)
    write_products_to_excel(products, out_path=out_path, template_path=template_path)
    print("[3/3] Готово к завершению", flush=True)
    return products


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="scraper",
        description=(
            "Сбор данных о товарах с сайта/раздела и экспорт в Excel.\n"
            "Поддерживается извлечение из JSON-LD, OpenGraph и эвристики."
        ),
    )
    p.add_argument("url", help="Ссылка на сайт или раздел сайта")
    p.add_argument(
        "-o",
        "--out",
        dest="out_path",
        default="products.xlsx",
        help="Путь для сохранения Excel (по умолчанию products.xlsx)",
    )
    p.add_argument(
        "-t",
        "--template",
        dest="template_path",
        default=None,
        help="Путь к Excel-шаблону (необязательно)",
    )
    p.add_argument(
        "-l",
        "--limit",
        dest="limit",
        type=int,
        default=100,
        help="Ограничение количества товаров для извлечения",
    )
    p.add_argument(
        "-d",
        "--delay",
        dest="delay",
        type=float,
        default=0.3,
        help="Задержка между запросами (сек)",
    )
    p.add_argument(
        "-H",
        "--user-agent",
        dest="user_agent",
        default=None,
        help="Переопределить User-Agent",
    )
    p.add_argument(
        "-r",
        "--retries",
        dest="retries",
        type=int,
        default=5,
        help="Количество повторов при ошибках HTTP",
    )
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    try:
        products = scrape_to_excel(
            url=args.url,
            out_path=args.out_path,
            template_path=args.template_path,
            limit=args.limit,
            delay=args.delay,
            user_agent=args.user_agent,
            retries=args.retries,
        )
        print(f"Парсинг успешно завершён. Сохранено товаров: {len(products)}")
        print(f"Файл: {args.out_path}")
        return 0
    except KeyboardInterrupt:
        print("Прервано пользователем", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Ошибка парсинга: {exc}", file=sys.stderr)
        return 1

