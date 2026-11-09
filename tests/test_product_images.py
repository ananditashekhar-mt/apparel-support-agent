"""Catalogue photos must cover real variants and follow products across gift purchases."""
import json
import unittest
from pathlib import Path
from product_art import product_image_path


class ProductImagesTests(unittest.TestCase):
    def test_every_order_has_its_exact_variant_photo(self):
        orders=json.loads((Path(__file__).resolve().parents[1]/'data/orders.json').read_text())
        paths={}
        for order in orders:
            key=tuple(order[k] for k in ('Product_Name','Colour','Gender'))
            path=product_image_path(order)
            self.assertIsNotNone(path,key)
            paths[key]=path
            gifted=dict(order,Is_Gift=True,Recipient_Gender='Other')
            self.assertEqual(product_image_path(gifted),path)
        self.assertEqual(len(paths),60)
        self.assertEqual(len(set(paths.values())),60)
