"""
Web product scraper package.

Exports:
- Product: dataclass representing a product
- scrape_to_excel: high-level function to run scraping flow and save to Excel
"""

from .types import Product
from .cli import scrape_to_excel

__all__ = ["Product", "scrape_to_excel"]

