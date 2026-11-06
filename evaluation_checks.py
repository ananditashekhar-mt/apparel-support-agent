"""Fixture diagnostics, separate from agent quality scores."""
def audit_references(rows, orders):
    conflicts=[]
    post_delivery={'return_request','exchange_size','exchange_color','fit_issue','damaged_item','wrong_item','quality_issue'}
    for row in rows:
        order=orders.get(row['Order_ID'])
        if not order:
            conflicts.append({'conversation_id':row['Conversation_ID'],'reason':'Unknown order'})
        elif row['Intent'] in post_delivery and order['Order_Status']!='Delivered':
            conflicts.append({'conversation_id':row['Conversation_ID'],'reason':'Post-delivery reference requires review against undelivered order'})
    train={r['Customer_Message'] for r in rows if r['Split']=='train'}
    test={r['Customer_Message'] for r in rows if r['Split']=='test'}
    return {'reference_cases_needing_review':conflicts,
            'distinct_messages_shared_between_train_and_test':sorted(train & test)}


def score_reference(row,result):
    # These compare fixture labels, not independently verified policy correctness.
    escalation=result.get('pending') is not None and result['pending']['kind']=='escalation'
    expected=row['Escalate'].strip().lower()
    return {'escalation_label_agreement': escalation==(expected=='yes') if expected in ('yes','no') else None}
