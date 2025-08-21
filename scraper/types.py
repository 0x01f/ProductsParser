from dataclasses import dataclass
from typing import Optional


@dataclass
class Product:
    name: str
    price: Optional[str]
    url: str
    image_url: Optional[str]
    description: Optional[str] = None

