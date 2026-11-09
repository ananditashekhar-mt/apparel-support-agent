import csv
import copy
import hashlib
import html
import io
import json
import os
import uuid
import traceback
from pathlib import Path
from datetime import date
from urllib.parse import urlencode
import streamlit.components.v1 as components

import streamlit as st
from dotenv import load_dotenv

from agent import Agent, load
from dataset import DEFAULT_DATE, order_as_of
from product_art import product_image_path

load_dotenv()
APP_ENV=os.getenv('APP_ENV','local' if (Path(__file__).parent/'.env').is_file() else 'hosted').lower()
BRAND_NAME=os.getenv('BRAND_NAME','Threadly')
AGENT_NAME=os.getenv('AGENT_NAME','Tia')
st.set_page_config(page_title=BRAND_NAME, page_icon='🧵', layout='wide', initial_sidebar_state='collapsed')
st.markdown('<style>'+(Path(__file__).parent/'ui'/'threadly.css').read_text()+'</style>',unsafe_allow_html=True)
PHONE_PREVIEW=st.query_params.get('phone_preview')=='1'
if PHONE_PREVIEW:
    st.markdown('<style>[data-testid=stSidebar],[data-testid=stSidebarCollapsedControl],[data-testid=stHeader]{display:none}.block-container{padding:16px 10px 10px!important}</style>',unsafe_allow_html=True)
    if 'simulation_date' not in st.session_state:
        try:
            preview_date=date.fromisoformat(st.query_params.get('as_of',''))
            if date(2026,10,1)<=preview_date<=date(2026,12,31):st.session_state.simulation_date=preview_date
        except ValueError:pass


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
if PHONE_PREVIEW:interface='Customer'

configured_mode=os.getenv('APP_MODE','OpenAI' if APP_ENV=='hosted' else 'Demo').title()
if configured_mode not in ['Demo','Openai','Ollama','Gemini','Groq']:configured_mode='Demo'
configured_mode='OpenAI' if configured_mode=='Openai' else configured_mode
for key,value in [('admin_openai_model',os.getenv('OPENAI_MODEL','gpt-4.1-mini' if APP_ENV=='hosted' else '')),
                  ('admin_ollama_model',os.getenv('OLLAMA_MODEL','')),
                  ('admin_gemini_model',os.getenv('GEMINI_MODEL','gemini-2.5-flash')),
                  ('admin_groq_model',os.getenv('GROQ_MODEL','openai/gpt-oss-20b')),
                  ('admin_input_rate',float(os.getenv('OPENAI_INPUT_USD_PER_M','0') or 0)),
                  ('admin_output_rate',float(os.getenv('OPENAI_OUTPUT_USD_PER_M','0') or 0)),
                  ('admin_usd_inr',float(os.getenv('USD_INR_RATE','0') or 0))]:
    if key not in st.session_state:st.session_state[key]=value
mode=configured_mode
model=st.session_state.get('admin_'+mode.lower()+'_model','')
input_rate=st.session_state.admin_input_rate;output_rate=st.session_state.admin_output_rate
usd_inr=st.session_state.admin_usd_inr
if interface=='Customer':
    with st.sidebar.expander('Demo settings',expanded=False):
        if os.getenv('ALLOW_MODE_SWITCH','false' if APP_ENV=='hosted' else 'true').lower()=='true':
            choices=['Demo','OpenAI','Gemini','Groq','Ollama']
            preview_mode=st.query_params.get('mode') if PHONE_PREVIEW else None
            mode=st.radio('Assistant',choices,index=choices.index(preview_mode if preview_mode in choices else configured_mode),horizontal=True)
            st.caption('Demo is deterministic. OpenAI, Gemini, Groq and Ollama add model-based understanding and writing; business rules remain in code.')
        else:st.caption(f'Assistant: {mode}')
        model=st.session_state.get('admin_'+mode.lower()+'_model','')
        demo_date=st.date_input('Simulation date',value=DEFAULT_DATE, key='simulation_date', help='October–December 2026. Earlier dates hide future orders and shipment events.')
        st.caption('All customers, orders and actions are synthetic.')
else:
    demo_date=DEFAULT_DATE

from database import database_fingerprint
@st.cache_resource(show_spinner=False)
def preserve_hosted_database(database_key):
    from hosted_cutover import preserve_and_import
    return preserve_and_import(Path(__file__).parent/'runtime_india_2026.sqlite',
                               os.getenv('DATABASE_URL_UNPOOLED') or os.environ['DATABASE_URL'])

if APP_ENV=='hosted' and os.getenv('DATABASE_URL'):
    try:
        preserve_hosted_database(database_fingerprint())
    except Exception:
        st.error('The database cutover needs review. Existing data has not been overwritten. Please contact the app owner.')
        st.stop()

agent_key=(mode,model,load('dataset_manifest')['Version'],'item-condition-v1',database_fingerprint())
if st.session_state.get('agent_key')!=agent_key:
    if st.session_state.get('agent'):st.session_state.agent.db.close()
    st.session_state.agent=Agent(mode=mode,model=model)
    st.session_state.agent_key=agent_key
agent=st.session_state.agent
if hasattr(agent.db,'check_connection'):agent.db.check_connection()


def reset_customer_state(cid,new=False):
    key=(cid,mode)
    if st.session_state.get('customer_key')!=key or new:
        st.session_state.customer_key=key;st.session_state.conversation_id=str(uuid.uuid4())
        st.session_state.chat_stage='order';st.session_state.selected_order=None
        st.session_state.unlisted_issue=False
        st.session_state.pending_order_request=None
        st.session_state.recent_origin=None
        st.session_state.show_all_orders=False
        st.session_state.pop('issue_description',None)
        st.session_state.history=[]
        st.session_state.pop('request_error',None)
        st.session_state.memory={};st.session_state.last=None;st.session_state.condition_ok=False


def feedback_state():
    # Persist the two-round limit across page reloads and reopening saved chats.
    row=agent.db.execute('SELECT payload FROM chat_feedback WHERE conversation_id=?',(st.session_state.conversation_id,)).fetchone()
    return json.loads(row[0]) if row else {'rounds':0,'phase':'open','support_result':None}


def save_feedback(state):
    agent.db.execute('INSERT OR REPLACE INTO chat_feedback VALUES(?,?)',
        (st.session_state.conversation_id,json.dumps(state)));agent.db.commit()



def ask_to_close(cid,state):
    if not state.get('wrapup_pending'):
        agent.log_message(st.session_state.conversation_id,cid,'assistant','Is there anything else I can help you with?')
        agent.db.commit()
        state['wrapup_pending']=True
        save_feedback(state)


def answer_checkin(cid,answer,customer_text=None):
    state=feedback_state()
    agent.log_message(st.session_state.conversation_id,cid,'user',customer_text or answer)
    state['wrapup_pending']=False
    if answer=='No, end chat':
        state.update(phase='closed',csat_submitted=False,csat_skipped=False,csat_id=None)
        reply='You’re all set. I’ve ended this chat. Thanks for stopping by!'
    else:
        reply='Of course. What else would you like help with on this issue?'
    agent.log_message(st.session_state.conversation_id,cid,'assistant',reply)
    agent.db.commit()
    save_feedback(state)
    st.session_state.history=agent.messages(st.session_state.conversation_id,cid)
    st.rerun()


def handle_customer_message(prompt,cid):
    state=feedback_state()
    normal=' '.join(prompt.strip().lower().translate(str.maketrans('','','.,!?')).split())
    if state.get('wrapup_pending') and state['phase'] in ('open','retry'):
        if normal in ('no','no thanks','no thank you','nothing else','all done',"that's all",'that’s all'):
            answer_checkin(cid,'No, end chat',prompt)
        if normal in ('yes','yes please','i need more help'):
            answer_checkin(cid,'Yes, I need more help',prompt)
    state['wrapup_pending']=False
    save_feedback(state)
    st.session_state.unlisted_issue=True
    submit_message(prompt,cid)


def submit_message(prompt,cid):
    st.session_state.pop('request_error',None)
    feedback=feedback_state()
    if feedback['phase'] not in ['open','retry']:return
    try:
        with st.spinner('Checking your request…'):
            result=agent.chat(prompt,st.session_state.memory,st.session_state.history,demo_date,
                st.session_state.condition_ok,st.session_state.conversation_id,cid,input_rate,output_rate,usd_inr,
                [order['Order_ID'] for order in profiles[cid]['orders'] if order_as_of(order,demo_date)],customer_name=profiles[cid]['name'],
                review_unlisted=st.session_state.get('unlisted_issue',False),offer_order_picker=True)
        if not result.get('needs_order_selection') and (result.get('feedback_required') or feedback['phase']=='retry'):
            if result.get('pending',{} ) and result['pending']['kind']=='escalation':
                feedback['support_result']=result
            feedback.update(phase='rating',csat_submitted=False,csat_skipped=False,csat_id=None)
            save_feedback(feedback)
            agent.log_message(st.session_state.conversation_id,cid,'assistant',
                'Please let us know if there is anything else we can help you with.')
            agent.db.commit()
        feedback=feedback_state()
        feedback['wrapup_pending']=False
        save_feedback(feedback)
        if result.get('status')=='answered' and not result.get('pending') and feedback['phase'] in ('open','retry'):
            ask_to_close(cid,feedback)
        st.session_state.pending_order_request=prompt if result.get('needs_order_selection') else None
        st.session_state.unlisted_issue=False
        st.session_state.chat_stage='pick_order' if result.get('needs_order_selection') else 'chat'
        st.session_state.memory=result['memory'];st.session_state.last=result
        st.session_state.history=agent.messages(st.session_state.conversation_id,cid);st.rerun()
    except Exception as error:
        frames='; '.join(f'{Path(frame.filename).name}:{frame.lineno} in {frame.name}' for frame in traceback.extract_tb(error.__traceback__))
        agent.log_error(st.session_state.conversation_id,cid,RuntimeError(f'UI request failed: {type(error).__name__}; {frames}'))
        st.session_state.history=agent.messages(st.session_state.conversation_id,cid)
        # Hosted logs need a safe diagnostic; never print provider bodies or keys.
        status=getattr(error,'status_code',None)
        print(f'Threadly request failed: {type(error).__name__}; http_status={status if isinstance(status,int) else None}',flush=True)
        st.session_state.request_error='I’m sorry, I couldn’t check that just now. Please try again in a moment. Your order hasn’t been changed.'
        st.error(st.session_state.request_error)


def open_recent_chats():
    keys=['conversation_id','chat_stage','selected_order','memory','history','last','condition_ok','unlisted_issue','pending_order_request']
    st.session_state.recent_origin={key:copy.deepcopy(st.session_state.get(key)) for key in keys}
    st.session_state.chat_stage='recent'


def back_in_journey(stage):
    if stage=='recent':
        origin=st.session_state.get('recent_origin')
        if origin:
            for key,value in origin.items():st.session_state[key]=value
        else:st.session_state.chat_stage='order'
    elif stage=='review':st.session_state.chat_stage='recent'
    elif stage=='reopen':st.session_state.chat_stage='review'
    elif stage=='describe':
        st.session_state.chat_stage='issue';st.session_state.unlisted_issue=False
    elif stage=='issue':
        st.session_state.chat_stage='order';st.session_state.memory={};st.session_state.selected_order=None
        st.session_state.condition_ok=False;st.session_state.last=None
    elif stage=='pick_order':
        st.session_state.chat_stage='issue';st.session_state.pending_order_request=None;st.session_state.last=None
    elif stage=='chat':
        st.session_state.chat_stage='review' if feedback_state()['phase'] not in ('open','retry') else 'issue'
        st.session_state.condition_ok=False
    elif stage=='order':st.session_state.chat_stage='chat'


def render_order_choices(cid,profile,resume=False):
    orders=sorted(profile['orders'],key=lambda o:(o['Order_Date'],o['Order_ID']),reverse=True)
    show_all=st.session_state.get('show_all_orders',False)
    st.caption('Your past orders · AI sample photos' if not show_all else 'All your orders · AI sample photos')
    for order in (orders if show_all else orders[:3]):
        with st.container(border=True,key='order_card_'+order['Order_ID']):
            photo,details,action=st.columns([1,6,3],vertical_alignment='center')
            image_path=product_image_path(order)
            if image_path:photo.image(str(image_path),width=48)
            with details:
                st.markdown(f'<div class="order-copy"><strong>{html.escape(order["Product_Name"])}</strong><span>{html.escape(order["Colour"])} · Size {html.escape(order["Size"])} · Qty {order["Qty"]}</span><span>{html.escape(order["Order_ID"])} · {html.escape(order["Order_Status"])}</span></div>',unsafe_allow_html=True)
            if action.button('Select order',key='choose_'+order['Order_ID'],width='stretch'):
                st.session_state.selected_order=order['Order_ID']
                if resume:
                    st.session_state.memory=dict(st.session_state.memory,order_id=order['Order_ID'])
                    submit_message('Please use '+order['Order_ID']+' for my question.',cid)
                else:
                    st.session_state.memory={'order_id':order['Order_ID']};st.session_state.last=None
                    st.session_state.condition_ok=False;st.session_state.chat_stage='issue';st.rerun()
    if len(orders)>3:
        if st.button('Show recent orders' if show_all else f'View all {len(orders)} orders',key='toggle_order_list'):
            st.session_state.show_all_orders=not show_all;st.rerun()

def open_saved_conversation(cid,conversation_id):
    agent.require_conversation_owner(conversation_id,cid)
    if st.session_state.chat_stage!='recent':open_recent_chats()
    st.session_state.conversation_id=conversation_id
    st.session_state.history=agent.messages(conversation_id,cid)
    saved=agent.db.execute('SELECT payload FROM events WHERE session=? ORDER BY rowid DESC LIMIT 1',(conversation_id,)).fetchone()
    result=json.loads(saved[0]) if saved else {}
    st.session_state.memory=result.get('memory',{});st.session_state.last=result or None
    st.session_state.condition_ok=result.get('condition_ok',False)
    st.session_state.selected_order=result.get('order_id');st.session_state.chat_stage='review'
    st.session_state.unlisted_issue=False


def queue_showcase(scenario):
    st.session_state.pending_showcase=scenario
    st.session_state.simulation_date=date.fromisoformat(scenario['As_Of'])


def customer_view():
    showcase=load('showcase_scenarios')
    with st.sidebar:
        st.markdown('**Showcase scenarios**')
        use_case=st.selectbox('Support use case',['Browse customers']+sorted({r['Use_Case'] for r in showcase}),key='showcase_use_case')
        scenario=None
        if use_case!='Browse customers':
            variants=sorted({r['Scenario_Variant'] for r in showcase if r['Use_Case']==use_case})
            variant=st.selectbox('Scenario variant',variants,key='showcase_variant')
            matches=[r for r in showcase if r['Use_Case']==use_case and r['Scenario_Variant']==variant]
            scenario=st.selectbox('Matching customer and order',matches,
                format_func=lambda r: f"{profiles[r['Customer_ID']]['name']} · {r['Order_ID']} · {r['As_Of']}",key='showcase_match')
            st.caption('Scenario date: '+scenario['As_Of'])
            st.button('Load scenario',key='load_showcase',on_click=queue_showcase,args=(scenario,))
    pending=st.session_state.pop('pending_showcase',None)
    visible={cid:dict(p,orders=[view for o in p['orders'] if (view:=order_as_of(o,demo_date))]) for cid,p in profiles.items()}
    visible={cid:p for cid,p in visible.items() if p['orders']}
    profile_options=sorted(visible,key=lambda c:(visible[c]['name'],visible[c]['city']))
    if not profile_options:
        st.info('No orders have been placed by the selected simulation date. Choose a date in October–December 2026.')
        return
    profile_labels={f"{visible[c]['name']} · {visible[c]['city']} · Customer {c[-4:]}":c for c in profile_options}
    if PHONE_PREVIEW and st.query_params.get('customer') in visible:
        requested_customer=st.query_params['customer']
        st.session_state.customer_profile_picker=next(label for label,c in profile_labels.items() if c==requested_customer)
    if pending:
        st.session_state.customer_profile_picker=next(label for label,c in profile_labels.items() if c==pending['Customer_ID'])
    if st.session_state.get('customer_profile_picker') not in profile_labels:
        st.session_state.customer_profile_picker=next(iter(profile_labels))
    with st.sidebar:
        selected_profile=st.selectbox('Preview customer',list(profile_labels),key='customer_profile_picker',help='Choose a synthetic Indian customer to preview their support experience.')
    cid=profile_labels[selected_profile]
    date_changed=st.session_state.get('active_simulation_date')!=demo_date.isoformat()
    reset_customer_state(cid,new=date_changed);profile=visible[cid]
    st.session_state.active_simulation_date=demo_date.isoformat()
    if pending:
        reset_customer_state(cid,True)
        st.session_state.selected_order=pending['Order_ID']
        st.session_state.memory={'order_id':pending['Order_ID']}
        st.session_state.chat_stage='issue'
        st.session_state.loaded_showcase=pending
    loaded=st.session_state.get('loaded_showcase')
    if loaded and loaded['Customer_ID']==cid and loaded['Order_ID']==st.session_state.selected_order and loaded['As_Of']==demo_date.isoformat():
        st.info(loaded['Use_Case']+' · '+loaded['Scenario_Variant']+' · '+loaded['As_Of'])
        st.caption('Example customer message: '+loaded['Customer_Message'])
        if st.button('Ask Tia this example',key='ask_showcase'):
            st.session_state.condition_ok=loaded['Condition_OK']
            submit_message(loaded['Customer_Message'],cid)
            st.rerun()
    if st.session_state.get('request_error'):st.error(st.session_state.request_error)
    brand,account=st.columns([2,1])
    with brand:
        st.markdown(f'<div class="brand-lockup"><div class="brand-mark">T</div><div class="brand-word">{html.escape(BRAND_NAME)}</div><div class="brand-sub">Customer care</div></div>',unsafe_allow_html=True)
    with account:
        st.markdown(f'<div class="account"><b>{html.escape(profile["name"])}</b> · {html.escape(profile["city"])}</div>',unsafe_allow_html=True)
    st.write('')
    if not PHONE_PREVIEW:
        with st.container(key='demo_view_switch'):
            view=st.radio('Demo view',['Desktop','Mobile'],horizontal=True,key='demo_view')
        if view=='Mobile':
            st.caption('Phone preview · 390 px · A separate chat for the selected customer')
            params=urlencode({'phone_preview':'1','embed':'true','customer':cid,'as_of':demo_date.isoformat(),'mode':mode})
            with st.container(key='demo_phone_frame'):
                components.iframe('?'+params,width=390,height=760,scrolling=True)
            return
    with st.sidebar:
        st.divider()
        st.caption('YOUR CONVERSATIONS')
        for conversation in agent.customer_conversations(cid)[:12]:
            label=agent.conversation_label(conversation['id'],cid)+' · '+conversation['updated_at'][:10]
            if st.button(label,key='history_'+conversation['id'],width='stretch'):
                open_saved_conversation(cid,conversation['id']);st.rerun()
        st.divider()
        st.caption('Demo experience · Orders and requests are examples. No live fulfilment or external support connection.')
    with st.container(key='care_workspace'):
        with st.container(key='chat_toolbar'):
            header,controls=st.columns([3,2],vertical_alignment='center')
            with header:
                st.markdown('<div class="assistant-header"><div class="tia-avatar">T</div><div><strong>Tia</strong><span>Your shopping sidekick · AI</span></div></div>',unsafe_allow_html=True)
            with controls:
                new,past=st.columns(2)
                if new.button('＋ New chat',key='new_chat_rail',width='stretch',type='primary'):
                    reset_customer_state(cid,True);st.rerun()
                if past.button('Past chats',key='rail_history',width='stretch'):
                    open_recent_chats();st.rerun()
        selected=st.session_state.selected_order
        order=next((o for o in profile['orders'] if o['Order_ID']==selected),None)
        if order and st.session_state.chat_stage not in ('order','pick_order','recent'):
            with st.expander(order['Product_Name']+' · '+selected):
                photo,details=st.columns([1,7])
                image_path=product_image_path(order)
                if image_path:photo.image(str(image_path),width=48)
                details.caption(f"{order['Colour']} · Size {order['Size']} · Qty {order['Qty']} · {order['Order_Status']}")
                if st.button('Change order'):
                    st.session_state.chat_stage='order';st.session_state.memory={}
                    st.session_state.selected_order=None;st.session_state.last=None
                    st.session_state.condition_ok=False;st.rerun()
                for event in order.get('Shipment_Events',[]):st.caption(f"{event['Status']} · {str(event['Date'])[:10]}")
                for request in agent.order_requests(selected,cid,st.session_state.conversation_id):
                    st.info(f"{request['kind'].title()}: {request['status'].replace('_',' ')}. {request['note']}")
        with st.container(height=450,border=False,key='chat_transcript'):
            render_customer_journey(cid,profile)
        phase=feedback_state()['phase']
        disabled=phase not in ('open','retry') or st.session_state.chat_stage in ('recent','review','reopen')
        prompt=st.chat_input('Type your message…',key='customer_message',disabled=disabled)
        if prompt:handle_customer_message(prompt,cid)


def render_csat(cid,state,allow_retry=False):
    if state.get('csat_submitted') or state.get('csat_skipped'):
        if state.get('csat_submitted'):st.caption('Thank you. Your feedback has been saved.')
        return
    if not state.get('csat_id'):
        state['csat_id']=str(uuid.uuid4());save_feedback(state)
    with st.container(border=True):
        st.markdown('**How was your experience with Tia?**')
        st.caption('Your feedback helps us improve our support.')
        with st.form('csat_'+state['csat_id']):
            st.caption('Rate your experience')
            selected=st.feedback('stars',key='score_'+state['csat_id'])
            rating=selected+1 if selected is not None else None
            comment=st.text_area('Your feedback (optional)',key='comment_'+state['csat_id'],max_chars=2000,height=90)
            if st.form_submit_button('Submit feedback',type='primary'):
                try:
                    agent.save_csat(st.session_state.conversation_id,cid,state['csat_id'],rating,comment)
                    state['csat_submitted']=True
                    if allow_retry:
                        state['rounds']+=1
                        agent.log_message(st.session_state.conversation_id,cid,'user',f'Feedback: {rating}/5 stars'+(' · '+comment.strip() if comment.strip() else ''))
                        if rating>=4:
                            state['phase']='closed';text='Thank you for your feedback.'
                        elif state['rounds']<2:
                            state['phase']='retry';text='I’m sorry we haven’t resolved this. What would you like us to look at again?'
                        else:
                            state['phase']='handoff';text='I’m sorry we haven’t resolved this. A Support Expert can take a closer look. I can save your concern with this conversation for review.'
                        agent.log_message(st.session_state.conversation_id,cid,'assistant',text);agent.db.commit()
                    save_feedback(state)
                    st.session_state.history=agent.messages(st.session_state.conversation_id,cid);st.rerun()
                except ValueError as error:st.warning(str(error))
        if st.button('Skip feedback',key='skip_'+state['csat_id']):
            state['csat_skipped']=True
            if allow_retry:state['phase']='closed'
            save_feedback(state);st.rerun()

def offer_chat_choices(cid):
    reopen,new=st.columns(2)
    if reopen.button('Reopen chat',key='reopen_current',width='stretch',icon=':material/replay:'):
        st.session_state.chat_stage='reopen';st.rerun()
    if new.button('Start a new chat',key='new_from_chat',width='stretch',icon=':material/add:'):
        reset_customer_state(cid,True);st.rerun()


def render_evidence(cid,last):
    oid=(last or {}).get('order_id') or st.session_state.memory.get('order_id')
    intent=(last or {}).get('intent') or st.session_state.memory.get('intent')
    if intent not in ('damaged_item','wrong_item','quality_issue') or not oid:return
    if oid not in {o['Order_ID'] for o in profiles[cid]['orders']}:return
    session=st.session_state.conversation_id
    with st.container(border=True):
        st.markdown('**Add photos for your Support Expert**')
        st.caption('A clear photo of the damage and the full item will help us understand what happened. Up to 3 photos, 5 MB each. JPG, PNG or WebP.')
        existing=agent.photos(session,cid)
        if existing:
            st.success(f'{len(existing)} photo(s) saved with this conversation.')
            with st.expander('View saved photos'):
                for photo in existing:st.image(photo['data'],caption=photo['name'],width=180)
        if len(existing)<3:
            files=st.file_uploader('Choose photos',type=['jpg','jpeg','png','webp'],accept_multiple_files=True,key='damage_photos_'+session)
            if st.button('Save photos',key='save_photos',disabled=not files):
                try:
                    for photo in files:agent.add_photo(session,cid,oid,photo.name,photo.getvalue())
                    st.rerun()
                except ValueError as error:st.error(str(error))
        st.caption('Photos are saved for Support review. Tia does not assess the images or approve a replacement from them. You can request help without a photo.')

def render_customer_journey(cid,profile):
    stage=st.session_state.chat_stage
    if stage!='order' or st.session_state.history:
        if st.button('Back',key='journey_back',icon=':material/arrow_back:'):
            back_in_journey(stage);st.rerun()
    if stage=='pick_order':
        for message in agent.messages(st.session_state.conversation_id,cid)[-2:]:render_message(message)
        render_order_choices(cid,profile,resume=True)
        return
    if stage=='recent':
        st.subheader('Your previous chats')
        st.caption('Pick a conversation to read it or reopen it.')
        conversations=agent.customer_conversations(cid)
        if not conversations:st.info('No previous chats yet. Start a new chat whenever you need help.')
        for conversation in conversations:
            label=agent.conversation_label(conversation['id'],cid)+' · '+conversation['updated_at'][:10]
            if st.button(label,key='recent_'+conversation['id'],width='stretch'):
                open_saved_conversation(cid,conversation['id']);st.rerun()
        return
    if stage in ('review','reopen'):
        with st.expander('Earlier conversation',expanded=stage=='review'):
            for message in agent.messages(st.session_state.conversation_id,cid):render_message(message)
        if stage=='review':
            state=feedback_state()
            if state['phase']=='closed':render_csat(cid,state)
            st.caption('Continue this conversation or start fresh for a different concern.')
            offer_chat_choices(cid)
        else:
            st.markdown('<div class="intro">I’m here to help. What brings you back to this conversation?</div>',unsafe_allow_html=True)
            with st.form('reopen_chat_'+st.session_state.conversation_id):
                reason=st.radio('Why are you reopening this chat?',['I was unhappy with the previous help','Something is still pending'],index=None)
                description=st.text_area('Tell us what still needs attention',max_chars=4000,placeholder='What wasn’t resolved, or what are you waiting for?')
                if st.form_submit_button('Reopen and continue',type='primary'):
                    try:
                        agent.reopen_conversation(st.session_state.conversation_id,cid,reason,description)
                        state=feedback_state();state.update(phase='open',rounds=0,support_result=None,csat_submitted=False,csat_skipped=False,csat_id=None,wrapup_pending=False);save_feedback(state)
                        st.session_state.history=agent.messages(st.session_state.conversation_id,cid)
                        st.session_state.chat_stage='chat';st.rerun()
                    except ValueError as error:st.warning(str(error))
            if st.button('Start a new chat',key='new_from_reopen',width='stretch'):
                reset_customer_state(cid,True);st.rerun()
        return
    if stage=='order':
        render_message({'role':'assistant','content':f"Hi {profile['name']}, I’m Tia.\nHow can I help you today?\n\nChoose a recent order, or type your question below."})
        render_order_choices(cid,profile)
        return
    if stage=='issue':
        render_message({'role':'assistant','content':'How can I help with this order?\nChoose a topic or tell me what happened below.'})
        topics=[('Delivery status','Where is my order?'),('Return an item','I would like to return my item.'),
                ('Exchange an item','I would like to exchange my item.'),('Delivery is late','My delivery is late.'),
                ('Damaged or faulty item','My item arrived damaged.'),('Wrong item received','I received the wrong item.'),
                ('An item is missing','An item is missing from my order.'),('Delivered, but not received','My order is marked delivered but I have not received it.'),
                ('Cancel an order','I would like to cancel my order.'),('Refund or payment help','I need help with my refund.')]
        icons=['local_shipping','keyboard_return','swap_horiz','schedule','broken_image','inventory_2','package_2','location_off','cancel','payments']
        with st.container(key='topic_grid'):
            for index,(label,prompt) in enumerate(topics):
                if st.button(label,key='topic_'+str(index),icon=':material/'+icons[index]+':',width='stretch'):
                    submit_message(prompt,cid)
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
    history=st.session_state.history
    if len(history)>4:
        with st.expander(f'Earlier messages ({len(history)-4})'):
            for message in history[:-4]:render_message(message)
    for message in history[-4:]:render_message(message)

    last=st.session_state.last
    render_evidence(cid,last)
    needs_condition=feedback_state()['phase'] in ['open','retry'] and last and last.get('status')=='needs_information' and last.get('intent') in ['return_request','exchange_size','exchange_color','fit_issue'] and not last.get('condition_ok')
    if needs_condition:
        st.session_state.condition_ok=st.checkbox('The item is unworn, unwashed, unaltered, unstained, and has its original tags.',value=st.session_state.condition_ok)
        if st.session_state.condition_ok and st.button('Continue eligibility check',type='primary'):
            submit_message('Yes, condition confirmed',cid)
    feedback=feedback_state()
    if feedback['phase']=='rating':
        render_csat(cid,feedback,allow_retry=True)
    elif feedback['phase']=='closed':
        st.caption('This chat has ended. You can reopen it or start a new chat below.')
        render_csat(cid,feedback)
    elif feedback['phase']=='handoff':
        st.caption('You can request a Support Expert below, reopen this chat, or start a new one.')
    if feedback['phase']=='handoff' and feedback.get('support_result'):
        last=feedback['support_result']
    show_action=feedback['phase']!='closed'
    if last and last.get('pending') and show_action and last['as_of']==demo_date.isoformat():
        label={'return':'Request a return','exchange':'Request an exchange','cancellation':'Cancel order','escalation':'Request a Support Expert'}[last['pending']['kind']]
        if st.button(label,type='primary'):
            try:
                request=agent.confirm(last,st.session_state.conversation_id)
                message=f'Thank you for sharing this with me. Your request {request} and conversation are saved for a Support Expert to review. This is a demo, so a live expert has not been contacted.' if last['pending']['kind']=='escalation' else f'Your request {request} is saved. You can follow its progress here. This demo does not change a real order.'
                agent.log_message(st.session_state.conversation_id,cid,'assistant',message);agent.db.commit()
                st.session_state.history.append({'role':'assistant','content':message})
                feedback.update(phase='open',wrapup_pending=False)
                save_feedback(feedback)
                ask_to_close(cid,feedback)
                st.session_state.last=None;st.rerun()
            except ValueError as error:st.error(str(error))
        st.caption('Includes this conversation · Demo request')
    if feedback['phase'] in ('closed','handoff'):
        offer_chat_choices(cid)
    elif feedback['phase'] in ('open','retry'):
        with st.container(key='end_chat_actions'):
            if feedback.get('wrapup_pending'):
                with st.container(key='chat_checkin'):
                    yes,no=st.columns(2)
                    if yes.button('Yes, I need more help',key='continue_after_checkin'):
                        answer_checkin(cid,'Yes, I need more help')
                    if no.button('No, end chat',key='close_after_checkin'):
                        answer_checkin(cid,'No, end chat')
            elif st.button('End chat',key='finish_chat'):
                ask_to_close(cid,feedback);st.rerun()


def to_csv(rows):
    output=io.StringIO();writer=csv.DictWriter(output,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
    return output.getvalue()


def render_message(message,show_meta=False):
    role=message['role'];is_user=role=='user';avatar='You' if is_user else 'T'
    safe=''.join('<p>'+html.escape(part).replace('\n','<br>')+'</p>' for part in str(message['content']).split('\n\n') if part.strip())
    meta=''
    if show_meta:meta=f'<div style="color:#7a8582;font-size:.75rem;margin-top:5px">{html.escape(message.get("created_at", ""))} · {html.escape(message.get("mode", ""))}</div>'
    checkin=' checkin-question' if message['content']=='Is there anything else I can help you with?' else ''
    st.markdown(f'''<div class="chat-row {'user' if is_user else 'assistant'}{checkin}">
        <div class="chat-avatar {'you' if is_user else 'tia'}">{avatar}</div>
        <div class="chat-bubble">{safe}{meta}</div></div>''',unsafe_allow_html=True)


def access_allowed(env_name,label):
    access_code=os.getenv(env_name)
    if access_code and st.text_input(f'{label} access code',type='password')!=access_code:
        st.info(f'Enter the {label.lower()} access code to continue.');return False
    if not access_code and APP_ENV=='hosted':
        st.warning(f'{label} is unavailable until its access code is configured in Streamlit secrets.')
        return False
    if not access_code:
        st.caption(f'Local demo: {label.lower()} access is open on this computer. Configure {env_name} before hosting.')
    return True


def support_view():
    st.title('Support')
    st.caption('Customer conversations and service requests')
    if not access_allowed('SUPPORT_ACCESS_CODE','Support'):return
    chats,requests,feedback_tab=st.tabs(['Customer chats','Requests','CSAT & feedback'])
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
            for response in agent.csat_responses(chosen):
                st.write(f"Customer satisfaction: {response['rating']}/5")
                if response['comment']:st.write(response['comment'])
            for photo in agent.photos(chosen):
                st.image(photo['data'],caption=photo['name']+' · '+photo['order_id'],width=240)
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


    with feedback_tab:
        st.subheader('CSAT & feedback')
        st.caption('CSAT: percentage of submitted ratings that are 4 or 5 out of 5.')
        responses=agent.support_feedback()
        if not responses:st.info('No ratings yet. Customers can rate their experience and leave a comment when they finish a chat.')
        else:
            a,b,c=st.columns(3)
            a.metric('Responses',len(responses))
            b.metric('Average rating',f"{sum(r['rating'] for r in responses)/len(responses):.1f} / 5")
            c.metric('CSAT',f"{sum(r['rating']>=4 for r in responses)/len(responses):.0%}")
            ratings=st.multiselect('Filter ratings',[1,2,3,4,5],default=[1,2,3,4,5])
            comments_only=st.checkbox('Only responses with written feedback')
            visible=[{'customer_name':profiles.get(r['customer_id'],{}).get('name','Unknown customer'),**r}
                     for r in responses if r['rating'] in ratings and (not comments_only or r['comment'])]
            if not visible:st.info('No feedback matches these filters.')
            else:
                st.dataframe(visible,hide_index=True,width='stretch')
                st.download_button('Download feedback CSV',to_csv(visible),'threadly-feedback.csv','text/csv')
                selected=st.selectbox('Feedback details',[r['feedback_id'] for r in visible],
                    format_func=lambda key:next(f"{r['customer_name']} · {r['rating']}/5 · {r['created_at'][:16]}" for r in visible if r['feedback_id']==key))
                response=next(r for r in visible if r['feedback_id']==selected)
                st.write(response['comment'] or 'No written comment provided.')
                st.caption('Conversation: '+response['conversation_id'])
                tickets=[r for r in agent.support_actions() if r['conversation_id']==response['conversation_id']]
                if tickets:st.dataframe(tickets,hide_index=True,width='stretch')
                else:st.caption('No service request was created for this conversation.')
                with st.expander('View conversation'):
                    for message in agent.messages(response['conversation_id']):render_message(message,show_meta=True)


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
        st.subheader('Jev shadow decisions')
        st.caption('Experimental judgments only. They do not change replies, eligibility, CSAT closure or handoffs. Jev usage is separate from the model cost totals above.')
        shadows=agent.shadow_rows()
        if shadows:
            st.json(shadows[:100],expanded=False)
            st.download_button('Download Jev shadow results',json.dumps(shadows,indent=2),'jev-shadow.json','application/json')
        else:st.info('No Jev shadow decisions recorded. Enable JEV_SHADOW_ENABLED and configure TYPESAFE_API_KEY to collect comparisons.')
        log_path=os.path.join(os.path.dirname(__file__),'logs','app.log')
        if os.path.exists(log_path):
            with open(log_path,encoding='utf-8',errors='replace') as handle:log_text=handle.read()
            st.caption('Rotating technical log. Customer message text and API keys are not recorded here.')
            st.code('\n'.join(log_text.splitlines()[-200:]) or 'No diagnostic events yet.')
            st.download_button('Download diagnostic log',log_text,'apparelcare-diagnostic.log','text/plain')
        else:st.info('No diagnostic events have been written yet.')
    with configuration:
        st.subheader('Database storage')
        if getattr(agent.db,'backend','sqlite')=='postgres':
            st.success('PostgreSQL connected. Conversations, tickets and feedback use hosted storage.')
        else:
            st.warning('SQLite local storage. Back up runtime data before rebuilding this host.')
        st.subheader('Model configuration')
        c1,c2,c3=st.columns(3)
        c1.metric('API key','Configured' if os.getenv(mode.upper()+'_API_KEY') else 'Missing')
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
            new_gemini_model=st.text_input('Gemini model ID',value=st.session_state.admin_gemini_model)
            new_groq_model=st.text_input('Groq model ID',value=st.session_state.admin_groq_model)
            new_ollama_model=st.text_input('Ollama model name',value=st.session_state.admin_ollama_model)
            new_input=st.number_input('Input price ($ / 1M tokens)',min_value=0.0,value=float(input_rate),step=0.01)
            new_output=st.number_input('Output price ($ / 1M tokens)',min_value=0.0,value=float(output_rate),step=0.01)
            new_inr=st.number_input('USD to INR rate',min_value=0.0,value=float(usd_inr),step=0.1)
            if st.form_submit_button('Apply for this session'):
                st.session_state.admin_gemini_model=new_gemini_model.strip();st.session_state.admin_groq_model=new_groq_model.strip();st.session_state.admin_openai_model=new_openai_model.strip();st.session_state.admin_ollama_model=new_ollama_model.strip();st.session_state.admin_input_rate=new_input
                st.session_state.admin_output_rate=new_output;st.session_state.admin_usd_inr=new_inr;st.rerun()
    with reference:
        st.subheader('Policies');st.dataframe(load('policies'),hide_index=True,width='stretch')
        st.subheader('Evaluation rubric');st.dataframe(load('evaluation_rubric'),hide_index=True,width='stretch')


if interface=='Customer':customer_view()
elif interface=='Support':support_view()
else:admin_view()
