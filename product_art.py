"""Exact catalogue-variant paths for locally hosted AI demo photographs."""
import re
from pathlib import Path

ASSETS=Path(__file__).parent/'assets'/'products'


def product_image_path(order):
    identity='-'.join(str(order.get(field,'')) for field in ('Product_Name','Colour','Gender'))
    filename=re.sub(r'[^a-z0-9]+','-',identity.lower()).strip('-')+'.png'
    path=ASSETS/filename
    return path if path.is_file() else None
