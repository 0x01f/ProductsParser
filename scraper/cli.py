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


MESSAGES = {
    "ru": {
        "stage_links": "[1/3] Определение типа страницы и сбор ссылок…",
        "found_product_page": "Найдено: страница товара. Всего к обработке: {total}",
        "found_links": "Найдено ссылок на товары: {found}. Будет обработано: {total}",
        "progress": "[{current}/{total}] ({percent}%) Обработка: {url} (осталось: {remaining})",
        "progress_ok": "[{current}/{total}] Успешно",
        "progress_fail": "[{current}/{total}] Не удалось извлечь данные",
        "warn_failed": "[warn] не удалось получить/извлечь {url}: {error}",
        "stage_save": "[2/3] Сохранение в Excel…",
        "stage_done": "[3/3] Готово к завершению",
        "success": "Парсинг успешно завершён. Сохранено товаров: {count}",
        "file": "Файл: {path}",
        "error": "Ошибка парсинга: {error}",
        "interrupted": "Прервано пользователем",
        "help_desc": (
            "Сбор данных о товарах с сайта/раздела и экспорт в Excel.\n"
            "Поддерживается извлечение из JSON-LD, OpenGraph и эвристики."
        ),
        "help_url": "Ссылка на сайт или раздел сайта",
        "help_out": "Путь для сохранения Excel (по умолчанию products.xlsx)",
        "help_template": "Путь к Excel-шаблону (необязательно)",
        "help_limit": "Ограничение количества товаров для извлечения",
        "help_delay": "Задержка между запросами (сек)",
        "help_ua": "Переопределить User-Agent",
        "help_retries": "Количество повторов при ошибках HTTP",
        "help_lang": "Язык сообщений: ru или en (по умолчанию ru)",
    },
    "en": {
        "stage_links": "[1/3] Detecting page type and collecting links…",
        "found_product_page": "Detected product page. Total to process: {total}",
        "found_links": "Found product links: {found}. Will process: {total}",
        "progress": "[{current}/{total}] ({percent}%) Processing: {url} (remaining: {remaining})",
        "progress_ok": "[{current}/{total}] Success",
        "progress_fail": "[{current}/{total}] Failed to extract data",
        "warn_failed": "[warn] failed to fetch/extract {url}: {error}",
        "stage_save": "[2/3] Saving to Excel…",
        "stage_done": "[3/3] Finalizing",
        "success": "Parsing has been successfully completed. Saved products: {count}",
        "file": "File: {path}",
        "error": "Parsing error: {error}",
        "interrupted": "Interrupted by user",
        "help_desc": (
            "Collect product data from a site/section and export to Excel.\n"
            "Extraction via JSON-LD, OpenGraph and DOM heuristics."
        ),
        "help_url": "URL of site or section",
        "help_out": "Path to Excel output (default products.xlsx)",
        "help_template": "Path to Excel template (optional)",
        "help_limit": "Maximum number of products to extract",
        "help_delay": "Delay between requests (sec)",
        "help_ua": "Override User-Agent",
        "help_retries": "Retry count for HTTP errors",
        "help_lang": "Messages language: ru or en (default ru)",
    },
}


def _msg(lang: str, key: str, **kwargs) -> str:
    lang_key = lang if lang in MESSAGES else "ru"
    template = MESSAGES[lang_key].get(key, "")
    return template.format(**kwargs)


def scrape_to_excel(
    url: str,
    out_path: str,
    template_path: Optional[str] = None,
    limit: int = 100,
    delay: float = 0.3,
    user_agent: Optional[str] = None,
    retries: int = 5,
    lang: str = "ru",
) -> List[Product]:
    """High-level convenience function: scrape products from URL and save into Excel.

    Returns the list of extracted products.
    """
    session = create_session(user_agent=user_agent, total_retries=retries)

    print(_msg(lang, "stage_links"), flush=True)
    final_url, html = fetch_html(url, session=session)
    is_product_page, product_links = discover_product_links(final_url, html, max_links=limit)

    products: List[Product] = []
    if is_product_page or not product_links:
        total = 1
        print(_msg(lang, "found_product_page", total=total), flush=True)
        print(_msg(lang, "progress", current=1, total=total, percent=int(round(1 * 100 / total)), url=final_url, remaining=total - 1), flush=True)
        product = extract_product(final_url, html)
        if product:
            products.append(product)
            print(_msg(lang, "progress_ok", current=1, total=total), flush=True)
        else:
            print(_msg(lang, "progress_fail", current=1, total=total), flush=True)
    else:
        total = min(limit, len(product_links))
        print(_msg(lang, "found_links", found=len(product_links), total=total), flush=True)
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
                print(_msg(lang, "progress", current=current, total=total, percent=int(round(current * 100 / total)), url=link, remaining=remaining), flush=True)
                _, p_html = fetch_html(link, session=session, pause_seconds=delay)
                product = extract_product(link, p_html)
                if product:
                    products.append(product)
                    print(_msg(lang, "progress_ok", current=current, total=total), flush=True)
                else:
                    print(_msg(lang, "progress_fail", current=current, total=total), flush=True)
                processed += 1
            except Exception as exc:
                print(_msg(lang, "warn_failed", url=link, error=exc), file=sys.stderr)

            if len(products) >= limit:
                break

    print(_msg(lang, "stage_save"), flush=True)
    write_products_to_excel(products, out_path=out_path, template_path=template_path)
    print(_msg(lang, "stage_done"), flush=True)
    return products


def _build_arg_parser(lang: str = "ru") -> argparse.ArgumentParser:
    loc = MESSAGES.get(lang, MESSAGES["ru"])  # use ru for help text by default
    p = argparse.ArgumentParser(
        prog="scraper",
        description=loc["help_desc"],
    )
    p.add_argument("url", help=loc["help_url"])
    p.add_argument(
        "-o",
        "--out",
        dest="out_path",
        default="products.xlsx",
        help=loc["help_out"],
    )
    p.add_argument(
        "-t",
        "--template",
        dest="template_path",
        default=None,
        help=loc["help_template"],
    )
    p.add_argument(
        "-l",
        "--limit",
        dest="limit",
        type=int,
        default=100,
        help=loc["help_limit"],
    )
    p.add_argument(
        "-d",
        "--delay",
        dest="delay",
        type=float,
        default=0.3,
        help=loc["help_delay"],
    )
    p.add_argument(
        "-H",
        "--user-agent",
        dest="user_agent",
        default=None,
        help=loc["help_ua"],
    )
    p.add_argument(
        "-r",
        "--retries",
        dest="retries",
        type=int,
        default=5,
        help=loc["help_retries"],
    )
    p.add_argument(
        "--lang",
        dest="lang",
        choices=["ru", "en"],
        default=lang,
        help=loc["help_lang"],
    )
    return p


def main(argv: Optional[list[str]] = None) -> int:
    # First parse with default RU help, then reparse if different lang requested isn't possible without two passes.
    parser = _build_arg_parser("ru")
    args = parser.parse_args(argv)
    lang = args.lang
    try:
        products = scrape_to_excel(
            url=args.url,
            out_path=args.out_path,
            template_path=args.template_path,
            limit=args.limit,
            delay=args.delay,
            user_agent=args.user_agent,
            retries=args.retries,
            lang=lang,
        )
        print(_msg(lang, "success", count=len(products)))
        print(_msg(lang, "file", path=args.out_path))
        return 0
    except KeyboardInterrupt:
        print(_msg(lang, "interrupted"), file=sys.stderr)
        return 130
    except Exception as exc:
        print(_msg(lang, "error", error=exc), file=sys.stderr)
        return 1

