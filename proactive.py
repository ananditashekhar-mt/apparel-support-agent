"""Preview scheduled post-purchase updates; does not send customer messages."""
import argparse
import json
from datetime import date
from agent import load

def updates(as_of):
    result=[]
    for order in load('orders'):
        status=order['Order_Status']
        promised=date.fromisoformat(order['Promised_Delivery'][:10])
        if status in ['Cancelled','Delivered']:continue
        if as_of<date.fromisoformat(order['Order_Date'][:10]):continue
        if promised<as_of:
            message=f"Your order {order['Order_ID']} is recorded as {status.lower()} and is past its promised delivery date. A fresh carrier check is needed; this dataset has no live scans."
            event='delay_review'
        elif status=='Out for Delivery':
            message=f"Your order {order['Order_ID']} is recorded as out for delivery with {order['Carrier']}. Tracking: {order['Tracking_ID']}. This is a synthetic status preview."
            event='delivery_update'
        else:continue
        result.append({'event_id':f"{order['Order_ID']}:{event}:{as_of.isoformat()}",'order_id':order['Order_ID'],'type':event,'message_preview':message})
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--date',default='2026-09-17');args=p.parse_args()
    print(json.dumps({'as_of':args.date,'preview_only':True,'updates':updates(date.fromisoformat(args.date))},indent=2))
