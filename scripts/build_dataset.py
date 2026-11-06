"""Deterministically enrich Threadly's dataset into a connected, scenario-rich set.

Reads the immutable data/source/orders.json, data/product_catalog.json and
data/support_conversations.json and rewrites them (plus a new data/customers.json)
with:
  - A first-class customer entity (data/customers.json) instead of a UI-side hash.
  - Customer_ID on every order and support conversation.
  - A synthetic Shipment_Events history per order (placed/shipped/in transit/
    out for delivery/delivered/cancelled/exception), grounded in each order's
    existing dates and carrier.
  - Delivered_Qty + Issue_Type ("Damaged", "Wrong Item", "Quality Issue",
    "Partial Delivery") on a subset of delivered orders, cross-referenced with
    the matching scenarios already described in support_conversations.json so
    the operational data and the eval fixtures agree with each other.
  - A dozen brand-new "Confirmed" (placed, not yet shipped) orders appended at
    the end, because the original dataset had none and cancel_order could
    never actually succeed.

This script only touches data/*.json (operational + reference data). It never
reads or writes support_conversations.json's Expected_* columns, so eval
fixtures stay decoupled from runtime state. Re-running it regenerates the same
output because every derived value comes from a stable hash of an existing ID,
never from an unseeded random source.
"""
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA = ROOT / 'data'

HUBS = {
    'Pune': 'Pune Fulfilment Center', 'Bengaluru': 'Bengaluru Fulfilment Center',
    'Delhi': 'Delhi Fulfilment Center', 'Mumbai': 'Mumbai Fulfilment Center',
    'Hyderabad': 'Hyderabad Fulfilment Center', 'Chennai': 'Chennai Fulfilment Center',
    'Kolkata': 'Kolkata Fulfilment Center', 'Gurugram': 'Gurugram Fulfilment Center',
    'Jaipur': 'Jaipur Fulfilment Center', 'Noida': 'Noida Fulfilment Center'}
DELAY_REASONS = [
    'Weather disruption at the regional hub', 'High parcel volume during a sale weekend',
    'Address verification required', 'Awaiting carrier pickup window',
    'Vehicle breakdown on the delivery route']
ISSUE_NOTES = {
    'Damaged': 'Customer reported the item arrived damaged in transit.',
    'Wrong Item': 'Customer reported a different product than ordered.',
    'Quality Issue': 'Customer reported a fabric or stitching defect.',
    'Partial Delivery': 'Only part of the order quantity arrived; the remaining unit is reported missing.'}
CONVERSATION_ISSUE_MAP = {'damaged_item': 'Damaged', 'wrong_item': 'Wrong Item', 'quality_issue': 'Quality Issue'}


def load(name):
    return json.loads((DATA / f'{name}.json').read_text())


def save(name, rows):
    (DATA / f'{name}.json').write_text(json.dumps(rows, indent=2) + '\n')


def stable_int(seed):
    return int(hashlib.sha256(seed.encode()).hexdigest(), 16)


def pick(seed, options):
    return options[stable_int(seed) % len(options)]


def hub(city):
    return HUBS.get(city, f'{city} Fulfilment Center')


def shift(date_text, **delta):
    return (datetime.fromisoformat(date_text) + timedelta(**delta)).strftime('%Y-%m-%d %H:%M:%S')


def build_customers(orders):
    customers = {}
    for order in orders:
        key = (order['Customer_Name_Synthetic'], order['City'])
        customers.setdefault(key, []).append(order['Order_Date'])
    rows = []
    for index, ((name, city), order_dates) in enumerate(sorted(customers.items(), key=lambda kv: min(kv[1])), start=1):
        cid = 'CUST-' + hashlib.sha256(f'{name}|{city}'.lower().encode()).hexdigest()[:10].upper()
        local = f'{name.lower()}{stable_int(name + city) % 90 + 10}'
        rows.append({
            'Customer_ID': cid, 'Name': name, 'City': city,
            'Email': f'{local}@example.test',
            'Phone': f'+91-9{stable_int(name + city + "phone") % 10**8:08d}',
            'Member_Since': min(order_dates)[:10]})
    return rows, {(row['Name'], row['City']): row['Customer_ID'] for row in rows}


def build_events(order):
    events = []
    events.append({'Status': 'Order Placed', 'Date': order['Order_Date'], 'Location': order['City'],
                    'Note': 'Order confirmed and payment captured.'})
    status = order['Order_Status']
    if status == 'Confirmed':
        return events
    if status == 'Cancelled':
        events.append({'Status': 'Order Cancelled', 'Date': shift(order['Order_Date'], hours=6),
                        'Location': order['City'], 'Note': 'Cancelled before handover to carrier.'})
        return events
    shipped = order.get('Shipped_Date')
    if not shipped:
        return events
    events.append({'Status': 'Shipped', 'Date': shipped, 'Location': hub(order['City']),
                    'Note': f"Handed to {order['Carrier']}."})
    if status in ('In Transit', 'Out for Delivery', 'Delivered', 'Delayed'):
        transit_city = pick(order['Order_ID'] + 'hub', [c for c in HUBS if c != order['City']] or [order['City']])
        events.append({'Status': 'In Transit', 'Date': shift(shipped, days=1), 'Location': hub(transit_city),
                        'Note': f"Moving through the {order['Carrier']} network."})
    if status == 'Delayed':
        reason = pick(order['Order_ID'] + 'delay', DELAY_REASONS)
        events.append({'Status': 'Delivery Exception', 'Date': shift(order['Promised_Delivery'], hours=4),
                        'Location': hub(order['City']), 'Note': reason + '.'})
    if status in ('Out for Delivery', 'Delivered'):
        anchor = order.get('Delivered_Date') or order['Promised_Delivery']
        events.append({'Status': 'Out for Delivery', 'Date': shift(anchor, hours=-5),
                        'Location': order['City'], 'Note': f"With the {order['Carrier']} courier for final mile delivery."})
    if status == 'Delivered':
        events.append({'Status': 'Delivered', 'Date': order['Delivered_Date'], 'Location': order['City'],
                        'Note': 'Received by customer.'})
        if order.get('Issue_Type'):
            events.append({'Status': f"{order['Issue_Type']} Reported", 'Date': order['Issue_Reported_Date'],
                            'Location': order['City'], 'Note': ISSUE_NOTES[order['Issue_Type']]})
    return events


def assign_issue_types(orders_by_id):
    conversations = sorted(load('support_conversations'), key=lambda c: c['Conversation_ID'])
    for conversation in conversations:
        issue = CONVERSATION_ISSUE_MAP.get(conversation['Intent'])
        order = orders_by_id.get(conversation['Order_ID'])
        if not issue or not order or order['Order_Status'] != 'Delivered' or order.get('Issue_Type'):
            continue
        order['Issue_Type'] = issue
        order['Issue_Reported_Date'] = shift(order['Delivered_Date'], days=1)
    partial_candidates = sorted(
        (o for o in orders_by_id.values() if o['Order_Status'] == 'Delivered' and o['Qty'] == 2 and not o.get('Issue_Type')),
        key=lambda o: stable_int(o['Order_ID'] + 'partial'))
    for order in partial_candidates[:10]:
        order['Delivered_Qty'] = 1
        order['Issue_Type'] = 'Partial Delivery'
        order['Issue_Reported_Date'] = shift(order['Delivered_Date'], days=1)


def build_confirmed_orders(customer_lookup, catalog, start_id):
    customers = sorted(customer_lookup.items(), key=lambda kv: kv[1])
    picks = [customers[i * len(customers) // 12] for i in range(12)]
    stock_rows = [row for row in catalog if row['Status'] == 'Active' and row['Stock_Qty'] > 0]
    carriers = ['Delhivery', 'Xpressbees', 'Blue Dart', 'Ecom Express']
    payments = ['UPI', 'Credit Card', 'Debit Card', 'COD']
    new_orders = []
    for index, ((name, city), cid) in enumerate(picks):
        order_id = f'ORD-{start_id + index}'
        row = stock_rows[stable_int(order_id + 'sku') % len(stock_rows)]
        qty = 1 + stable_int(order_id + 'qty') % 2
        new_orders.append({
            'Order_ID': order_id, 'Customer_Name_Synthetic': name, 'City': city, 'Customer_ID': cid,
            'SKU': row['SKU'], 'Product_Name': row['Product_Name'], 'Category': row['Category'],
            'Gender': row['Gender'], 'Size': row['Size'], 'Colour': row['Colour'], 'Qty': qty,
            'Order_Date': '2026-09-16 00:00:00', 'Shipped_Date': None,
            'Promised_Delivery': '2026-09-23 00:00:00', 'Delivered_Date': None,
            'Order_Status': 'Confirmed', 'Carrier': pick(order_id + 'carrier', carriers),
            'Tracking_ID': f'TRK{stable_int(order_id + "trk") % 10**8:08d}',
            'Order_Total_INR': row['Price_INR'] * qty,
            'Payment_Method': pick(order_id + 'pay', payments),
            'Delivered_Qty': 0, 'Issue_Type': None, 'Issue_Reported_Date': None})
    return new_orders


def main():
    orders = json.loads((DATA / 'source' / 'orders.json').read_text())
    catalog = load('product_catalog')
    customers, customer_lookup = build_customers(orders)

    for order in orders:
        order['Customer_ID'] = customer_lookup[(order['Customer_Name_Synthetic'], order['City'])]
        order['Delivered_Qty'] = order['Qty'] if order['Order_Status'] == 'Delivered' else 0
        order.setdefault('Issue_Type', None)
        order.setdefault('Issue_Reported_Date', None)

    orders_by_id = {o['Order_ID']: o for o in orders}
    assign_issue_types(orders_by_id)

    next_id = max(int(o['Order_ID'].split('-')[1]) for o in orders) + 1
    new_orders = build_confirmed_orders(customer_lookup, catalog, next_id)

    ordered_fields = ['Order_ID', 'Customer_Name_Synthetic', 'City', 'Customer_ID', 'SKU', 'Product_Name',
                       'Category', 'Gender', 'Size', 'Colour', 'Qty', 'Order_Date', 'Shipped_Date',
                       'Promised_Delivery', 'Delivered_Date', 'Order_Status', 'Carrier', 'Tracking_ID',
                       'Order_Total_INR', 'Payment_Method', 'Delivered_Qty', 'Issue_Type',
                       'Issue_Reported_Date', 'Shipment_Events']
    all_orders = orders + new_orders
    final_orders = []
    for order in all_orders:
        order['Shipment_Events'] = build_events(order)
        # Preserve lifecycle order when source dates have only day precision.
        for previous, event in zip(order['Shipment_Events'], order['Shipment_Events'][1:]):
            event['Date'] = max(previous['Date'], event['Date'])
        final_orders.append({key: order[key] for key in ordered_fields})

    conversations = load('support_conversations')
    orders_by_id = {o['Order_ID']: o for o in final_orders}
    final_conversations = []
    for conversation in conversations:
        order = orders_by_id.get(conversation['Order_ID'])
        reordered = {}
        for key, value in conversation.items():
            reordered[key] = value
            if key == 'Order_ID':
                reordered['Customer_ID'] = order['Customer_ID'] if order else None
        final_conversations.append(reordered)

    save('customers', customers)
    save('orders', final_orders)
    save('support_conversations', final_conversations)
    print(f'customers: {len(customers)} | orders: {len(final_orders)} (+{len(new_orders)} new) | '
          f'conversations: {len(final_conversations)}')
    issue_counts = {}
    for order in final_orders:
        if order['Issue_Type']:
            issue_counts[order['Issue_Type']] = issue_counts.get(order['Issue_Type'], 0) + 1
    print('Issue_Type distribution:', issue_counts)
    print('Confirmed (cancellable) orders added:', [o['Order_ID'] for o in new_orders])


if __name__ == '__main__':
    main()
