import csv
import hashlib
import html
import io
import json
import os
import uuid
import traceback
from pathlib import Path
from datetime import date

import streamlit as st
from dotenv import load_dotenv

from agent import Agent, load

load_dotenv()
BRAND_NAME=os.getenv('BRAND_NAME','Threadly')
AGENT_NAME=os.getenv('AGENT_NAME','Tia')
st.set_page_config(page_title=BRAND_NAME, page_icon='🧵', layout='wide', initial_sidebar_state='collapsed')
st.markdown('''<style>
.stApp {background:#f3f4f8;color:#292c38}
.block-container {max-width:1180px;padding:3.7rem 1.5rem 3rem}
[data-testid="stHeader"] {background:#f3f4f8}
[data-testid="stSidebar"] {background:#fff;border-right:1px solid #e7e8ef}
[data-testid="stVerticalBlock"] {gap:.75rem}
h1,h2,h3 {color:#282636;letter-spacing:-.025em}
h3 {font-size:1.25rem!important;padding:0!important;margin:0!important}
p {font-size:.94rem;line-height:1.55}
.brand-lockup {display:flex;align-items:center;gap:9px}
.brand-mark {width:32px;height:32px;border-radius:10px;background:#40365c;color:#fff;display:grid;place-items:center;font:italic 23px Georgia,serif}
.brand-word {font:600 24px Georgia,serif;color:#302a42}
.brand-sub {font:400 13px sans-serif;color:#777885;margin-left:10px;border-left:1px solid #d9dae4;padding-left:16px}
.account {text-align:right;font-size:13px;color:#737582;padding-top:8px}
.account b {color:#383344;font-weight:600}
.st-key-care_workspace {background:#fff;border:1px solid #e4e4ed;border-radius:20px;padding:24px;box-shadow:0 8px 32px #28233d07;min-height:530px}
.st-key-care_rail {padding:8px 16px 0 0}
.st-key-care_rail [data-testid="stCaptionContainer"] p {font-size:12px}
.assistant-header {display:flex;align-items:center;gap:11px;border-bottom:1px solid #eeeef4;padding-bottom:17px;margin-bottom:3px}
.tia-avatar {width:42px;height:42px;border-radius:50%;background:#ede9f6;color:#685491;display:grid;place-items:center;font-size:19px;font-weight:600}
.assistant-header strong {display:block;font-size:15px;font-weight:600;color:#2e293e}
.assistant-header span {font-size:12px;color:#85818f}
.intro {background:#f6f5fa;border-radius:3px 14px 14px;padding:14px 17px;color:#504a60;font-size:14px;line-height:1.6;margin:3px 0 10px;max-width:580px}
.context-label {font-size:11px;letter-spacing:.07em;color:#888492;text-transform:uppercase;margin:20px 0 10px}
.context-card {background:#ebeaf2;border-radius:14px;padding:16px;margin:4px 0 8px}
.context-card strong {display:block;font-size:15px;color:#393246;margin:9px 0 5px}
.context-card p {font-size:12px;color:#757080;margin:5px 0}
.context-pill {display:inline-block;font-size:11px;background:#fff;color:#596a60;padding:3px 8px;border-radius:6px}
.rail-note {font-size:12px;color:#85818e;line-height:1.6;margin-top:22px}
.stButton>button {border:1px solid #e4e2ed;border-radius:10px;min-height:43px;color:#4b435b;background:white;font-size:14px;justify-content:flex-start;padding:9px 13px;box-shadow:none}
.stButton>button p {font-size:14px;line-height:1.3}
.stButton>button:hover {background:#f5f2fa;border-color:#b8a8d0;color:#4d3a6d}
.stButton>button[kind="primary"] {background:#51416d;border-color:#51416d;color:#fff;justify-content:center}
.stButton>button[kind="primary"]:hover {background:#403156;color:white}
.st-key-care_workspace [data-testid="stExpander"] {border:1px solid #e8e6ef;border-radius:10px;background:#fbfaff}
.st-key-care_workspace [data-testid="stVerticalBlockBorderWrapper"] {border-radius:12px}
.chat-row {display:flex;gap:10px;align-items:flex-start;margin:12px 0}
.chat-avatar {width:28px;height:28px;min-width:28px;border-radius:50%;display:grid;place-items:center;font-size:10px;background:#eee9f6;color:#675182}
.chat-avatar.you {background:#e6edf2;color:#5e7182}
.chat-bubble {max-width:88%;padding:12px 15px;border-radius:3px 13px 13px;background:#f6f5fa;color:#4d465b;line-height:1.6;font-size:14px}
.chat-row.user {flex-direction:row-reverse}
.chat-row.user .chat-bubble {background:#eee9f7;border-radius:13px 3px 13px 13px}
[data-testid="stChatInput"] {border-radius:12px}
[data-testid="stBottom"] {background:transparent}
.mobile-order,.st-key-mobile_new_chat {display:none}
@media(max-width:640px) {.block-container {padding:3.7rem .8rem 2rem}.st-key-care_workspace {padding:18px;min-height:0}.st-key-care_rail {padding:0}.st-key-care_context {display:none}.st-key-mobile_new_chat {display:block}[data-testid="stColumn"]:has(.st-key-care_rail) {display:none}.st-key-care_rail {margin-bottom:0}.mobile-order {display:block;font-size:12px;color:#81798c}.st-key-topic_primary [data-testid="stHorizontalBlock"],.st-key-topic_secondary [data-testid="stHorizontalBlock"] {flex-wrap:nowrap!important;gap:8px}.st-key-topic_primary [data-testid="stColumn"],.st-key-topic_secondary [data-testid="stColumn"] {min-width:0!important;flex:1!important}.st-key-topic_primary button {padding:9px 8px}.st-key-topic_primary button p {font-size:12px}.brand-sub {display:none}.account {font-size:12px}.intro {font-size:14px}}
</style>''',unsafe_allow_html=True)


def customer_id(order):
    """Dataset Customer_ID is the identity; hash fallback covers older records only."""
    if order.get('Customer_ID'):return order['Customer_ID']
    seed=f"{order['Customer_Name_Synthetic']}|{order['City']}".lower()
    return 'CUST-'+hashlib.sha256(seed.encode()).hexdigest()[:10].upper()


orders=load('orders')
customers={c['Customer_ID']:c for c in load('customers')}
profiles={}
for order in orders:
    cid=customer_id(order)
    record=customers.get(cid,{})
    profiles.setdefault(cid,{'name':record.get('Name',order['Customer_Name_Synthetic']),
        'city':record.get('City',order['City']),'email':record.get('Email'),'orders':[]})['orders'].append(order)

with st.sidebar:
    st.markdown(f'<div class="brand-lockup"><div class="brand-mark">T</div><div class="brand-word">{html.escape(BRAND_NAME)}</div></div>',unsafe_allow_html=True)
    st.caption('A little care, beyond checkout.')
    interface=st.radio('Interface',['Customer','Support','Admin'])

configured_mode=os.getenv('APP_MODE','Demo').title()
if configured_mode not in ['Demo','Openai','Ollama']:configured_mode='Demo'
configured_mode='OpenAI' if configured_mode=='Openai' else configured_mode
for key,value in [('admin_openai_model',os.getenv('OPENAI_MODEL','')),
                  ('admin_ollama_model',os.getenv('OLLAMA_MODEL','')),
                  ('admin_input_rate',float(os.getenv('OPENAI_INPUT_USD_PER_M','0') or 0)),
                  ('admin_output_rate',float(os.getenv('OPENAI_OUTPUT_USD_PER_M','0') or 0)),
                  ('admin_usd_inr',float(os.getenv('USD_INR_RATE','0') or 0))]:
    if key not in st.session_state:st.session_state[key]=value
mode=configured_mode
model=st.session_state.admin_ollama_model if mode=='Ollama' else st.session_state.admin_openai_model
input_rate=st.session_state.admin_input_rate;output_rate=st.session_state.admin_output_rate
usd_inr=st.session_state.admin_usd_inr
if interface=='Customer':
    with st.sidebar.expander('Demo settings',expanded=False):
        if os.getenv('ALLOW_MODE_SWITCH','true').lower()=='true':
            choices=['Demo','OpenAI','Ollama']
            mode=st.radio('Assistant',choices,index=choices.index(configured_mode),horizontal=True)
            st.caption('Demo is deterministic. OpenAI and Ollama add model-based understanding and writing; business rules remain in code.')
        else:st.caption(f'Assistant: {mode}')
        model=st.session_state.admin_ollama_model if mode=='Ollama' else st.session_state.admin_openai_model
        demo_date=st.date_input('Simulation date',value=date(2026,9,17),help='The sample orders use fixed dates.')
        st.caption('All customers, orders and actions are synthetic.')
else:
    demo_date=date(2026,9,17)

agent_key=(mode,model,'feedback-v2')
if st.session_state.get('agent_key')!=agent_key:
    if st.session_state.get('agent'):st.session_state.agent.db.close()
    st.session_state.agent=Agent(mode=mode,model=model)
    st.session_state.agent_key=agent_key
agent=st.session_state.agent


def reset_customer_state(cid,new=False):
    key=(cid,mode)
    if st.session_state.get('customer_key')!=key or new:
        st.session_state.customer_key=key;st.session_state.conversation_id=str(uuid.uuid4())
        st.session_state.chat_stage='order';st.session_state.selected_order=None
        st.session_state.unlisted_issue=False
        st.session_state.pop('issue_description',None)
        st.session_state.history=[]
        st.session_state.memory={};st.session_state.last=None;st.session_state.condition_ok=False


def feedback_state():
    # Persist the two-round limit across page reloads and reopening saved chats.
    agent.db.execute('CREATE TABLE IF NOT EXISTS chat_feedback (conversation_id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
    row=agent.db.execute('SELECT payload FROM chat_feedback WHERE conversation_id=?',(st.session_state.conversation_id,)).fetchone()
    return json.loads(row[0]) if row else {'rounds':0,'phase':'open','support_result':None}


def save_feedback(state):
    agent.db.execute('INSERT OR REPLACE INTO chat_feedback VALUES(?,?)',
        (st.session_state.conversation_id,json.dumps(state)));agent.db.commit()


def submit_message(prompt,cid):
    feedback=feedback_state()
    if feedback['phase'] not in ['open','retry']:return
    try:
        with st.spinner('Checking your request…'):
            result=agent.chat(prompt,st.session_state.memory,st.session_state.history,demo_date,
                st.session_state.condition_ok,st.session_state.conversation_id,cid,input_rate,output_rate,usd_inr,
                [order['Order_ID'] for order in profiles[cid]['orders']],customer_name=profiles[cid]['name'],
                review_unlisted=st.session_state.get('unlisted_issue',False))
        if result.get('feedback_required') or feedback['phase']=='retry':
            if result.get('pending',{} ) and result['pending']['kind']=='escalation':
                feedback['support_result']=result
            feedback['phase']='rating'
            save_feedback(feedback)
            agent.log_message(st.session_state.conversation_id,cid,'assistant',
                'Please let us know if there is anything else we can help you with.')
            agent.db.commit()
        st.session_state.unlisted_issue=False
        st.session_state.chat_stage='chat'
        st.session_state.memory=result['memory'];st.session_state.last=result
        st.session_state.history=agent.messages(st.session_state.conversation_id,cid);st.rerun()
    except Exception as error:
        frames='; '.join(f'{Path(frame.filename).name}:{frame.lineno} in {frame.name}' for frame in traceback.extract_tb(error.__traceback__))
        agent.log_error(st.session_state.conversation_id,cid,RuntimeError(f'UI request failed: {type(error).__name__}; {frames}'))
        st.session_state.history=agent.messages(st.session_state.conversation_id,cid)
        st.error('I’m sorry, I couldn’t check that just now. Please try again in a moment. Your order hasn’t been changed.')


def customer_view():
    profile_options=sorted(profiles,key=lambda c:(profiles[c]['name'],profiles[c]['city']))
    profile_labels={f"{profiles[c]['name']} · {profiles[c]['city']} · Customer {c[-4:]}":c for c in profile_options}
    with st.sidebar:
        selected_profile=st.selectbox('Preview customer',list(profile_labels),key='customer_profile_picker',help='Choose a sample customer to preview their support experience.')
    cid=profile_labels[selected_profile]
    reset_customer_state(cid);profile=profiles[cid]
    brand,account=st.columns([2,1])
    with brand:
        st.markdown(f'<div class="brand-lockup"><div class="brand-mark">T</div><div class="brand-word">{html.escape(BRAND_NAME)}</div><div class="brand-sub">Customer care</div></div>',unsafe_allow_html=True)
    with account:
        st.markdown(f'<div class="account"><b>{html.escape(profile["name"])}</b> · {html.escape(profile["city"])}</div>',unsafe_allow_html=True)
    st.write('')
    with st.sidebar:
        st.divider()
        st.caption('YOUR CONVERSATIONS')
        for conversation in agent.customer_conversations(cid)[:12]:
            label='Chat · '+conversation['updated_at'][:10]
            if st.button(label,key='history_'+conversation['id'],width='stretch'):
                st.session_state.conversation_id=conversation['id']
                st.session_state.history=agent.messages(conversation['id'],cid)
                saved=agent.db.execute('SELECT payload FROM events WHERE session=? ORDER BY rowid DESC LIMIT 1',(conversation['id'],)).fetchone()
                result=json.loads(saved[0]) if saved else {}
                st.session_state.memory=result.get('memory',{});st.session_state.last=result or None
                st.session_state.condition_ok=result.get('condition_ok',False)
                st.session_state.selected_order=result.get('order_id');st.session_state.chat_stage='chat'
                st.session_state.unlisted_issue=False;st.rerun()
        st.divider()
        st.caption('Demo experience · Orders and requests are examples. No live fulfilment or external support connection.')
    with st.container(key='mobile_new_chat'):
        if st.button('＋ New chat',key='new_chat_mobile',type='primary',width='stretch'):
            reset_customer_state(cid,True);st.rerun()
    rail,workspace=st.columns([1,2.8],gap='large')
    with rail:
        with st.container(key='care_rail'):
            if st.button('＋ New chat',key='new_chat_rail',type='primary',width='stretch'):
                reset_customer_state(cid,True);st.rerun()
            with st.container(key='care_context'):
                st.markdown('<div class="context-label">Your order</div>',unsafe_allow_html=True)
                selected=st.session_state.selected_order
                order=next((o for o in profile['orders'] if o['Order_ID']==selected),None)
                if order:
                    status=order['Order_Status']
                    if any(r['kind']=='cancellation' and r['status']=='completed' for r in agent.order_requests(selected,cid,st.session_state.conversation_id)):status='Cancelled'
                    st.markdown(f'''<div class="context-card"><span class="context-pill">{html.escape(status)}</span><strong>{html.escape(order['Product_Name'])}</strong><p>{html.escape(selected)}</p><p>{html.escape(order['Colour'])} · Size {html.escape(order['Size'])} · Qty {order['Qty']}</p></div>''',unsafe_allow_html=True)
                    if st.button('Change order',width='stretch'):
                        reset_customer_state(cid,True);st.rerun()
                    with st.expander('Order updates'):
                        for event in order.get('Shipment_Events',[]):st.caption(f"{event['Status']} · {str(event['Date'])[:10]}")
                        for request in agent.order_requests(selected,cid,st.session_state.conversation_id):st.info(f"{request['kind'].title()}: {request['status'].replace('_',' ')}. {request['note']}")
                else:
                    st.caption('Select an order in the chat to get started.' if st.session_state.chat_stage=='order' else 'General question · No order selected')
                st.markdown('<div class="context-label">Need a closer look?</div><div class="rail-note">If I can’t resolve your concern, I’ll help you request a review from a Support Expert.</div>',unsafe_allow_html=True)
    with workspace:
        with st.container(key='care_workspace'):
            st.markdown('<div class="assistant-header"><div class="tia-avatar">T</div><div><strong>Tia</strong><span>Your Threadly care assistant</span></div></div>',unsafe_allow_html=True)
            selected=st.session_state.selected_order
            order=next((o for o in profile['orders'] if o['Order_ID']==selected),None)
            if order:st.markdown(f'<div class="mobile-order">{html.escape(order["Product_Name"])} · {html.escape(selected)}</div>',unsafe_allow_html=True)
            render_customer_journey(cid,profile)


def render_customer_journey(cid,profile):
    stage=st.session_state.chat_stage
    if stage=='order':
        st.markdown(f'<div class="intro">Hi {html.escape(profile["name"])}, I’m Tia. I can help with your delivery, a return, an exchange, or something else.<br>Which order is this about?</div>',unsafe_allow_html=True)
        for index,order in enumerate(sorted(profile['orders'],key=lambda o:o['Order_Date'],reverse=True)):
            with st.container(border=True):
                st.caption(order['Order_ID']+' · '+order['Order_Status'])
                st.markdown('**'+order['Product_Name']+'**')
                st.caption(f"{order['Colour']} · Size {order['Size']} · Qty {order['Qty']}")
                if st.button('Get help with this order',icon=':material/arrow_forward:',key='choose_'+order['Order_ID'],width='stretch'):
                    st.session_state.selected_order=order['Order_ID']
                    st.session_state.memory={'order_id':order['Order_ID']}
                    st.session_state.chat_stage='issue';st.rerun()
        if st.button('Other',icon=':material/chat_bubble_outline:',width='stretch'):
            st.session_state.selected_order=None;st.session_state.memory={}
            st.session_state.chat_stage='issue';st.rerun()
        return
    if stage=='issue':
        st.markdown('<div class="intro">Thanks. What would you like help with? Choose a topic below, or tell me what happened in your own words.</div>',unsafe_allow_html=True)
        topics=[('Delivery status','Where is my order?'),('Return an item','I would like to return my item.'),
                ('Exchange an item','I would like to exchange my item.'),('Delivery is late','My delivery is late.'),
                ('Damaged or faulty item','My item arrived damaged.'),('Wrong item received','I received the wrong item.'),
                ('An item is missing','An item is missing from my order.'),('Delivered, but not received','My order is marked delivered but I have not received it.'),
                ('Cancel an order','I would like to cancel my order.'),('Refund or payment help','I need help with my refund.')]
        icons=['local_shipping','keyboard_return','swap_horiz','schedule','broken_image','inventory_2','package_2','location_off','cancel','payments']
        with st.container(key='topic_primary'):
            columns=st.columns(3)
            for index,(label,prompt) in enumerate(topics[:3]):
                if columns[index].button(label,key='topic_'+str(index),icon=':material/'+icons[index]+':',width='stretch'):submit_message(prompt,cid)
        st.caption('More help with your order')
        with st.container(key='topic_secondary'):
            for index,(label,prompt) in enumerate(topics[3:],start=3):
                if (index-3)%2==0:columns=st.columns(2)
                if columns[(index-3)%2].button(label,key='topic_'+str(index),icon=':material/'+icons[index]+':',width='stretch'):submit_message(prompt,cid)
        if st.button('My issue is not listed here',width='stretch'):
            st.session_state.chat_stage='describe';st.session_state.unlisted_issue=True;st.rerun()
        if st.button('← Choose a different order'):
            st.session_state.chat_stage='order';st.session_state.memory={};st.rerun()
        return
    if stage=='describe':
        st.markdown('<div class="intro">Of course. Tell me what happened and how you’d like us to help. I’ll check the options for you. If this needs a Support Expert, I’ll help you with the next step.</div>',unsafe_allow_html=True)
        with st.form('describe_issue'):
            description=st.text_area('Describe your issue',key='issue_description',placeholder='What happened, and what would you like help with?',height=140,max_chars=4000)
            if st.form_submit_button('Let Tia take a look',type='primary'):
                if description.strip():submit_message(description.strip(),cid)
                else:st.warning('Please tell me a little about your issue so I can help.')
        if st.button('← Back to topics'):
            st.session_state.chat_stage='issue';st.session_state.unlisted_issue=False;st.rerun()
        return
    st.session_state.history=agent.messages(st.session_state.conversation_id,cid)
    for message in st.session_state.history:render_message(message)

    last=st.session_state.last
    needs_condition=feedback_state()['phase'] in ['open','retry'] and last and last.get('status')=='needs_information' and last.get('intent') in ['return_request','exchange_size','exchange_color','fit_issue'] and not last.get('condition_ok')
    if needs_condition:
        st.session_state.condition_ok=st.checkbox('The item is unworn, unwashed, unaltered, unstained, and has its original tags.',value=st.session_state.condition_ok)
        if st.session_state.condition_ok and st.button('Continue eligibility check',type='primary'):
            submit_message('Yes, condition confirmed',cid)
    feedback=feedback_state()
    if feedback['phase']=='rating':
        st.caption('Did this help with your concern?')
        rating=st.feedback('stars',key='rating_'+st.session_state.conversation_id+'_'+str(feedback['rounds']))
        if rating is not None:
            stars=rating+1
            feedback['rounds']+=1
            agent.log_message(st.session_state.conversation_id,cid,'user',f'Feedback: {stars}/5 stars')
            if stars>=4:
                feedback['phase']='closed'
                text='Thank you for your feedback.'
            elif feedback['rounds']<2:
                feedback['phase']='retry'
                text='I’m sorry we haven’t resolved this. How can we help you further?'
            else:
                feedback['phase']='handoff'
                text='I’m sorry we haven’t resolved this. You deserve a closer look from a Support Expert. I can save your concern and this conversation for review, so you won’t need to explain it all again. In this demo, no live expert is connected.'
            agent.log_message(st.session_state.conversation_id,cid,'assistant',text)
            save_feedback(feedback)
            st.session_state.history=agent.messages(st.session_state.conversation_id,cid);st.rerun()
    elif feedback['phase']=='closed':
        st.caption('Chat closed. Thank you for your feedback.')
    elif feedback['phase']=='handoff':
        st.caption('Chat closed. You can request support below or start a new chat for a different issue.')
    if feedback['phase']=='handoff' and feedback.get('support_result'):
        last=feedback['support_result']
    show_action=feedback['phase']!='closed'
    if last and last.get('pending') and show_action and last['as_of']==demo_date.isoformat():
        label={'return':'Request a return','exchange':'Request an exchange','cancellation':'Cancel order','escalation':'Request a Support Expert'}[last['pending']['kind']]
        c1,c2=st.columns([2,3])
        if c1.button(label,type='primary',width='stretch'):
            try:
                request=agent.confirm(last,st.session_state.conversation_id)
                message=f'Thank you for sharing this with me. Your request {request} and conversation are saved for a Support Expert to review. This is a demo, so a live expert has not been contacted.' if last['pending']['kind']=='escalation' else f'Your request {request} is saved. You can follow its progress here. This demo does not change a real order.'
                agent.log_message(st.session_state.conversation_id,cid,'assistant',message);agent.db.commit()
                st.session_state.history.append({'role':'assistant','content':message})
                if last['pending']['kind']=='escalation':
                    feedback['phase']='closed';save_feedback(feedback)
                st.session_state.last=None;st.rerun()
            except ValueError as error:st.error(str(error))
        c2.caption('Your conversation will be included with your request. Demo only; no live connection.')
    prompt=st.chat_input('Tell Tia a little more…',disabled=feedback['phase'] not in ['open','retry'])
    if prompt:submit_message(prompt,cid)


def to_csv(rows):
    output=io.StringIO();writer=csv.DictWriter(output,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
    return output.getvalue()


def render_message(message,show_meta=False):
    role=message['role'];is_user=role=='user';avatar='You' if is_user else 'Tia'
    safe=html.escape(str(message['content'])).replace('\n','<br>')
    meta=''
    if show_meta:meta=f'<div style="color:#7a8582;font-size:.75rem;margin-top:5px">{html.escape(message.get("created_at", ""))} · {html.escape(message.get("mode", ""))}</div>'
    st.markdown(f'''<div class="chat-row {'user' if is_user else 'assistant'}">
        <div class="chat-avatar {'you' if is_user else 'tia'}">{avatar}</div>
        <div class="chat-bubble">{safe}{meta}</div></div>''',unsafe_allow_html=True)


def access_allowed(env_name,label):
    access_code=os.getenv(env_name)
    if access_code and st.text_input(f'{label} access code',type='password')!=access_code:
        st.info(f'Enter the {label.lower()} access code to continue.');return False
    if not access_code:
        st.caption(f'Local demo: {label.lower()} access is open on this computer. Configure {env_name} before hosting.')
    return True


def support_view():
    st.title('Support')
    st.caption('Customer conversations and service requests')
    if not access_allowed('SUPPORT_ACCESS_CODE','Support'):return
    chats,requests=st.tabs(['Customer chats','Requests'])
    with chats:
        rows=agent.support_conversations()
        if not rows:st.info('No conversations have been logged yet.')
        else:
            for row in rows:row['customer_name']=profiles.get(row['customer_id'],{}).get('name','Unknown customer')
            rows=[{'customer_name':r['customer_name'],**r} for r in rows]
            st.dataframe(rows,hide_index=True,width='stretch')
            choices=[r['conversation_id'] for r in rows]
            labels={r['conversation_id']:f"{r['customer_name']} · {r['customer_id']} · {r['updated_at'].replace('T',' ')[:16]} · {r['messages']} messages" for r in rows}
            chosen=st.selectbox('Open transcript',choices,format_func=lambda x:labels.get(x,x),key='support_transcript')
            for message in agent.messages(chosen):
                render_message(message,show_meta=True)
    with requests:
        rows=agent.support_actions()
        if rows:
            st.dataframe(rows,hide_index=True,width='stretch')
            request_id=st.selectbox('Update request',[r['id'] for r in rows])
            request=next(r for r in rows if r['id']==request_id)
            with st.form('support_update_'+request_id):
                statuses=['pending','in_progress','completed','rejected']
                status=st.selectbox('Status',statuses,index=statuses.index(request['status']))
                assignee=st.text_input('Assigned to',value=request['assignee'])
                note=st.text_area('Reply visible to the customer',value=request['note'])
                st.caption('Updates are simulated. Completing a cancellation marks it cancelled in subsequent tracking replies.')
                if st.form_submit_button('Save update'):
                    agent.update_request(request_id,status,assignee,note);st.rerun()
        else:st.info('No mock requests have been created.')


def admin_view():
    st.title('Admin')
    st.caption('API cost, failures, technical logs, and application configuration')
    if not access_allowed('ADMIN_ACCESS_CODE','Admin'):return
    summary=agent.usage_summary();a,b,c,d=st.columns(4)
    a.metric('API requests',f"{summary['requests']:,}",border=True)
    b.metric('Input tokens',f"{summary['input_tokens']:,}",border=True)
    c.metric('Output tokens',f"{summary['output_tokens']:,}",border=True)
    cost=f"${summary['cost_usd']:.4f}"+(f" / ~₹{summary['cost_inr']:.0f}" if usd_inr else '')
    d.metric('Estimated cost',cost,border=True)
    if not input_rate and not output_rate:
        st.info('Token tracking is active. Configure the selected model’s token prices to calculate monetary cost.')
    else:
        st.caption(f'Cost basis: {model or "model not named"} · ${input_rate:g}/1M input · ${output_rate:g}/1M output · USD/INR {usd_inr:g}. Estimates are not invoices.')
    usage,failures,diagnostics,configuration,reference=st.tabs(['API usage','Errors & failures','Diagnostic log','Configuration','Reference'])
    with usage:
        rows=agent.usage_rows()
        if rows:st.dataframe(rows,hide_index=True,width='stretch')
        else:st.info('No model usage has been recorded. Demo messages do not consume tokens.')
        if rows:st.download_button('Download usage CSV',to_csv(rows),'model_usage.csv','text/csv')
    with failures:
        rows=agent.error_rows()
        if rows:st.dataframe(rows,hide_index=True,width='stretch')
        else:st.success('No failures have been logged.')
    with diagnostics:
        log_path=os.path.join(os.path.dirname(__file__),'logs','app.log')
        if os.path.exists(log_path):
            with open(log_path,encoding='utf-8',errors='replace') as handle:log_text=handle.read()
            st.caption('Rotating technical log. Customer message text and API keys are not recorded here.')
            st.code('\n'.join(log_text.splitlines()[-200:]) or 'No diagnostic events yet.')
            st.download_button('Download diagnostic log',log_text,'apparelcare-diagnostic.log','text/plain')
        else:st.info('No diagnostic events have been written yet.')
    with configuration:
        st.subheader('Model configuration')
        c1,c2,c3=st.columns(3)
        c1.metric('API key','Configured' if os.getenv('OPENAI_API_KEY') else 'Missing')
        c2.metric('Selected model',model or 'Missing')
        c3.metric('Default mode',configured_mode)
        st.write('For the complete app, keep credentials and pricing in the `.env` file beside `app.py`. Never paste the API key into customer-facing fields or commit `.env` to source control.')
        st.code('''OPENAI_API_KEY=your_private_key
OPENAI_MODEL=your_enabled_model_id
OLLAMA_MODEL=your_local_model_name
OLLAMA_BASE_URL=http://localhost:11434/v1
OPENAI_INPUT_USD_PER_M=published_input_price
OPENAI_OUTPUT_USD_PER_M=published_output_price
USD_INR_RATE=current_conversion_rate
APP_MODE=Demo
ALLOW_MODE_SWITCH=false
SUPPORT_ACCESS_CODE=choose_a_support_code
ADMIN_ACCESS_CODE=choose_a_different_admin_code''',language='text')
        st.caption('Restart Streamlit after changing `.env`. The API key is read from the environment and is never written to SQLite or the diagnostic log.')
        with st.form('session_cost_settings'):
            st.write('Temporary settings for this browser session')
            new_openai_model=st.text_input('OpenAI model ID',value=st.session_state.admin_openai_model)
            new_ollama_model=st.text_input('Ollama model name',value=st.session_state.admin_ollama_model)
            new_input=st.number_input('Input price ($ / 1M tokens)',min_value=0.0,value=float(input_rate),step=0.01)
            new_output=st.number_input('Output price ($ / 1M tokens)',min_value=0.0,value=float(output_rate),step=0.01)
            new_inr=st.number_input('USD to INR rate',min_value=0.0,value=float(usd_inr),step=0.1)
            if st.form_submit_button('Apply for this session'):
                st.session_state.admin_openai_model=new_openai_model.strip();st.session_state.admin_ollama_model=new_ollama_model.strip();st.session_state.admin_input_rate=new_input
                st.session_state.admin_output_rate=new_output;st.session_state.admin_usd_inr=new_inr;st.rerun()
    with reference:
        st.subheader('Policies');st.dataframe(load('policies'),hide_index=True,width='stretch')
        st.subheader('Evaluation rubric');st.dataframe(load('evaluation_rubric'),hide_index=True,width='stretch')


if interface=='Customer':customer_view()
elif interface=='Support':support_view()
else:admin_view()
