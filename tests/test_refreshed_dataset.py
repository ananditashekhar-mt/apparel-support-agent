"""Contract tests for the synthetic dataset, timeline projection and showcase."""
import json
import tempfile
import unittest
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch
from agent import Agent, ROOT, load, offline_parse
from dataset import DEFAULT_DATE, order_as_of


class DatasetContractTests(unittest.TestCase):
    def test_counts_identity_splits_and_purchase_history(self):
        customers=load('customers');orders=load('orders');rows=load('support_conversations')
        self.assertEqual((len(customers),len(orders),len(rows)),(200,600,1200))
        self.assertEqual(Counter(Counter(o['Customer_ID'] for o in orders).values()),{1:50,2:70,4:50,7:30})
        self.assertEqual(Counter(r['Split'] for r in rows),{'train':500,'showcase':100,'test':300,'challenge':200,'reserve':100})
        people={c['Customer_ID']:c for c in customers};by_order={o['Order_ID']:o for o in orders}
        self.assertEqual(len(people),200);self.assertEqual(len(by_order),600)
        self.assertGreater(len({c['Name'] for c in customers}),50)
        self.assertLess(len({c['Name'] for c in customers}),150)
        self.assertGreater(max(Counter(c['Name'] for c in customers).values()),2)
        for o in orders:
            c=people[o['Customer_ID']]
            self.assertEqual(o['Dataset_Split'],c['Dataset_Split'])
            self.assertEqual(o['Customer_Name_Synthetic'],c['Name'])
            self.assertEqual(o['Country'],'India')
            self.assertEqual(o['Recipient_Gender'],o['Gender'])
            self.assertEqual(o['Is_Gift'],c['Gender']!=o['Gender'])
        for r in rows:
            self.assertEqual(r['Split'],by_order[r['Order_ID']]['Dataset_Split'])
            self.assertEqual(r['Customer_ID'],by_order[r['Order_ID']]['Customer_ID'])
            self.assertTrue(all(by_order[oid]['Customer_ID']==r['Customer_ID'] for oid in r['Allowed_Order_IDs']))
        for split in ('train','showcase','test','challenge','reserve'):
            self.assertEqual({r['Intent'] for r in rows if r['Split']==split},{r['Intent'] for r in load('intent_taxonomy')}|{'unknown'})

    def test_timeline_prices_products_vendors_and_quantities(self):
        catalog={(r['SKU'],r['Size'],r['Colour']):r for r in load('product_catalog')}
        vendors={v['Vendor_ID'] for v in load('vendors')};carriers={r['Name'] for r in load('carriers')}
        months=set();delivery_months=set()
        for o in load('orders'):
            product=catalog[(o['SKU'],o['Size'],o['Colour'])]
            self.assertEqual(o['Vendor_ID'],product['Vendor_ID']);self.assertIn(o['Vendor_ID'],vendors)
            self.assertIn(o['Carrier'],carriers)
            self.assertEqual(o['Order_Total_INR'],o['Qty']*product['Price_INR'])
            dates=[e['Date'] for e in o['Shipment_Events']]
            self.assertEqual(dates,sorted(dates),o['Order_ID'])
            self.assertTrue(all('2026-10-01'<=d[:10]<='2026-12-31' for d in dates))
            self.assertTrue(all(d[:10]<=o['Snapshot_Date'] for d in dates),o['Order_ID'])
            months.add(o['Order_Date'][5:7])
            if o['Delivered_Date']:
                self.assertLess(o['Order_Date'],o['Shipped_Date']);self.assertLess(o['Shipped_Date'],o['Delivered_Date'])
                delivery_months.add(o['Delivered_Date'][5:7])
            if o['Issue_Type']=='Partial Delivery':self.assertLess(o['Delivered_Qty'],o['Qty'])
        self.assertEqual(months,{'10','11','12'});self.assertEqual(delivery_months,{'10','11','12'})

    def test_date_projection_does_not_leak_future_orders_or_events(self):
        for o in load('orders'):
            placed=date.fromisoformat(o['Order_Date'][:10])
            self.assertIsNone(order_as_of(o,placed-timedelta(days=1)))
            view=order_as_of(o,placed)
            self.assertFalse(any(e['Date'][:10]>placed.isoformat() for e in view['Shipment_Events']))
            self.assertEqual(view['Delivered_Qty'],0)
            self.assertIsNone(view['Issue_Type'])
            self.assertEqual(order_as_of(o,date.fromisoformat(o['Snapshot_Date'])),o)

    def test_catalogue_sizes_and_colours_are_understood(self):
        self.assertEqual(offline_parse('Exchange to size 32')['size'],'32')
        self.assertEqual(offline_parse('Size XL')['size'],'XL')
        self.assertIsNone(offline_parse('Return after 30 days')['size'])
        self.assertEqual(offline_parse('Exchange colour Dark Blue')['colour'],'Dark Blue')
        self.assertEqual(offline_parse('Exchange colour Olive')['colour'],'Olive')

    def test_showcase_is_public_and_covers_every_intent(self):
        cases=load('showcase_scenarios')
        self.assertEqual(len(cases),100)
        self.assertEqual({r['Intent'] for r in cases},{r['Intent'] for r in load('intent_taxonomy')}|{'unknown'})
        self.assertFalse(any(k.startswith('Expected_') for r in cases for k in r))
        for filename in ('agent.py','dataset.py','app.py'):
            source=(ROOT/filename).read_text()
            self.assertNotIn("load('support_conversations')",source)


class ShowcaseInterfaceTests(unittest.TestCase):
    def test_every_use_case_loads_matching_order_and_date(self):
        from streamlit.testing.v1 import AppTest
        original=Agent
        with tempfile.TemporaryDirectory() as t:
            def isolated(*args,**kwargs):
                kwargs['db_path']=Path(t)/'ui.sqlite';return original(*args,**kwargs)
            with patch('agent.Agent',side_effect=isolated):
                app=AppTest.from_file(str(ROOT/'app.py')).run()
                use_cases=next(w for w in app.selectbox if w.label=='Support use case').options[1:]
                for group in use_cases:
                    next(w for w in app.selectbox if w.label=='Support use case').set_value(group).run()
                    app.button(key='load_showcase').click().run()
                    self.assertEqual(len(app.exception),0,group)
                    row=app.session_state['loaded_showcase']
                    self.assertEqual(row['Use_Case'],group)
                    self.assertEqual(app.session_state['selected_order'],row['Order_ID'])
                    self.assertEqual(app.session_state['simulation_date'].isoformat(),row['As_Of'])
                    app.button(key='ask_showcase').click().run()
                    self.assertEqual(len(app.exception),0,group)
                    self.assertEqual(app.session_state['last']['order_id'],row['Order_ID'])
                app.session_state['agent'].db.close()
