"""Date-aware views of synthetic operational records; no evaluation labels."""
import copy
import json
from datetime import date
from pathlib import Path

DATA = Path(__file__).parent / 'data'
DEFAULT_DATE = date.fromisoformat(json.loads((DATA/'dataset_manifest.json').read_text())['Default_As_Of'])


def order_as_of(order, as_of):
    """Hide future orders and derive past status solely from recorded events.

    A snapshot is authoritative from its Snapshot_Date onward; no future scans
    or delivered quantities are invented when advancing beyond that date.
    """
    if not order:return None
    day=as_of.isoformat()
    if order['Order_Date'][:10]>day:return None
    result=copy.deepcopy(order)
    result['Shipment_Events']=[e for e in order.get('Shipment_Events',[]) if e['Date'][:10]<=day]
    if order.get('Snapshot_Date') and day<order['Snapshot_Date']:
        statuses={'Order Placed':'Confirmed','Order Cancelled':'Cancelled','Shipped':'Shipped',
                  'In Transit':'In Transit','Out for Delivery':'Out for Delivery','Delivered':'Delivered',
                  'Delivery Exception':'Delayed'}
        result['Order_Status']='Confirmed'
        for event in result['Shipment_Events']:
            if event['Status'] in statuses:result['Order_Status']=statuses[event['Status']]
        for key in ('Shipped_Date','Delivered_Date','Issue_Reported_Date'):
            if result.get(key) and result[key][:10]>day:result[key]=None
        if not result.get('Shipped_Date'):result['Tracking_ID']=None
        if not result.get('Delivered_Date'):
            result['Delivered_Qty']=0;result['Delivery_Disputed']=False
        elif not result.get('Issue_Reported_Date'):result['Delivered_Qty']=result['Qty']
        if not result.get('Issue_Reported_Date'):result['Issue_Type']=None
    return result
