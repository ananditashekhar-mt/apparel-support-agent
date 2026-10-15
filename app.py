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
st.set_page_config(page_title=BRAND_NAME, page_icon='🧵', layout='wide')
st.markdown('''<style>
.stApp {background:linear-gradient(180deg,#f8fbfa 0,#ffffff 320px);color:#253238}
.block-container {max-width:1180px;padding-top:1.4rem;padding-bottom:3rem}
[data-testid="stSidebar"] {background:#eef6f3;border-right:1px solid #d9e9e3}
[data-testid="stSidebar"] * {color:#253238}
h1,h2,h3 {color:#253238!important;letter-spacing:-.02em}
.brand-lockup {display:flex;align-items:center;gap:10px;margin:.15rem 0 .4rem}
.brand-mark {width:38px;height:38px;border-radius:12px;background:#e56b50;color:white;display:grid;place-items:center;font:800 22px/1 Georgia,serif;box-shadow:0 5px 14px rgba(229,107,80,.22)}
.brand-word {font-size:1.35rem;font-weight:800;letter-spacing:-.03em;color:#173f3a}
.threadly-hero {background:linear-gradient(120deg,#164e47,#2e7469);color:white;padding:28px 32px;border-radius:22px;margin:8px 0 22px;box-shadow:0 12px 35px rgba(22,78,71,.16)}
.threadly-hero h1 {color:white!important;margin:0;font-size:2.15rem}
.threadly-hero p {margin:.45rem 0 0;color:#fff3ee;font-size:1.05rem}
.order-card {background:white;border:1px solid #dce9e5;border-radius:18px;padding:18px 20px;margin:8px 0 20px;box-shadow:0 6px 20px rgba(23,63,58,.06)}
.order-card .eyebrow {color:#2e7469;font-size:.78rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em}
.order-card h3 {margin:.35rem 0 .2rem}
.status-pill {display:inline-block;background:#e1f1ec;color:#205b53;border-radius:999px;padding:4px 10px;font-size:.82rem;font-weight:650}
.chat-row {display:flex;gap:10px;align-items:flex-start;margin:10px 0}
.chat-avatar {width:30px;height:30px;min-width:30px;border-radius:10px;display:grid;place-items:center;font-size:13px;font-weight:800;margin-top:3px}
.chat-avatar.tia {background:#173f3a;color:#fff}
.chat-avatar.you {background:#fde7e0;color:#a94330}
.chat-bubble {max-width:84%;padding:11px 14px;border-radius:16px;line-height:1.5;border:1px solid #dce9e5;background:#fff}
.chat-row.user {flex-direction:row-reverse}
.chat-row.user .chat-bubble {background:#fff3ee;border-color:#f3d8cf}
.chat-row.user .chat-avatar {order:0}
[data-testid="stChatInput"] {background:white}
.stButton>button {border-radius:999px;border-color:#277267}
.stButton>button[kind="primary"] {background:#1d6259;border-color:#1d6259}
</style>''', unsafe_allow_html=True)


def customer_id(order):
    """Stable synthetic identity for this classroom prototype."""
    seed=f"{order['Customer_Name_Synthetic']}|{order['City']}".lower()
    return 'CUST-'+hashlib.sha256(seed.encode()).hexdigest()[:10].upper()


orders=load('orders')
profiles={}
for order in orders:
    cid=customer_id(order)
    profiles.setdefault(cid,{'name':order['Customer_Name_Synthetic'],'city':order['City'],'orders':[]})['orders'].append(order)

with st.sidebar:
    st.markdown(f'<div class="brand-lockup"><div class="brand-mark">T</div><div class="brand-word">{html.escape(BRAND_NAME)}</div></div>',unsafe_allow_html=True)
    st.caption(f'{AGENT_NAME} · post-purchase assistant')
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
    with st.sidebar:
        st.divider()
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
                [order['Order_ID'] for order in profiles[cid]['orders']],customer_name=profiles[cid]['name'])
        if result.get('feedback_required') or feedback['phase']=='retry':
            if result.get('pending',{} ) and result['pending']['kind']=='escalation':
                feedback['support_result']=result
            feedback['phase']='rating'
            save_feedback(feedback)
            agent.log_message(st.session_state.conversation_id,cid,'assistant',
                'Please let us know if there is anything else we can help you with.')
            agent.db.commit()
        st.session_state.memory=result['memory'];st.session_state.last=result
        st.session_state.history=agent.messages(st.session_state.conversation_id,cid);st.rerun()
    except Exception as error:
        frames='; '.join(f'{Path(frame.filename).name}:{frame.lineno} in {frame.name}' for frame in traceback.extract_tb(error.__traceback__))
        agent.log_error(st.session_state.conversation_id,cid,RuntimeError(f'UI request failed: {type(error).__name__}; {frames}'))
        st.session_state.history=agent.messages(st.session_state.conversation_id,cid)
        st.error('We could not complete that request. It has been logged for support review; no action was created.')


def customer_view():
    profile_options=sorted(profiles,key=lambda c:(profiles[c]['name'],profiles[c]['city']))
    profile_labels={f"{profiles[c]['name']} · {profiles[c]['city']} · Customer {c[-4:]}":c for c in profile_options}
    header_left,header_right=st.columns([3,2],vertical_alignment='center')
    with header_left:
        st.markdown(f'<div class="brand-lockup"><div class="brand-mark">T</div><div class="brand-word">{html.escape(BRAND_NAME)}</div></div>',unsafe_allow_html=True)
        st.caption('Everyday style, thoughtfully supported.')
    with header_right:
        selected_profile=st.selectbox('Shopping as',list(profile_labels),key='customer_profile_picker',
            help='Switch synthetic customers to test separate orders and chat histories.')
        cid=profile_labels[selected_profile]
    reset_customer_state(cid);profile=profiles[cid]
    st.markdown(f'''<div class="threadly-hero"><h1>Hello, {html.escape(profile['name'])} 👋</h1>
        <p>I’m {html.escape(AGENT_NAME)}, your {html.escape(BRAND_NAME)} care assistant. I can help with tracking, delivery issues, returns, and exchanges.</p></div>''',unsafe_allow_html=True)
    title_col,button_col=st.columns([5,1],vertical_alignment='center')
    with title_col:st.subheader('How can I help with your order?')
    with button_col:
        if st.button('＋ New chat',width='stretch'):reset_customer_state(cid,True);st.rerun()
    if mode=='OpenAI' and not os.getenv('OPENAI_API_KEY'):
        st.warning('OpenAI mode needs an API key. You can continue in Demo mode.')
    if mode=='Ollama':
        if not model:st.warning('Ollama mode needs an OLLAMA_MODEL value, such as the name of a model you have pulled.')
        else:st.info(f'Ollama will use {model}. Make sure the local Ollama service is running.')
    order_ids=[order['Order_ID'] for order in profile['orders']]
    order_labels={f"{order['Order_ID']} · {order['Product_Name']} · {order['Order_Status']}":order['Order_ID'] for order in profile['orders']}
    active_order=order_labels[st.selectbox('Order to discuss',list(order_labels))]
    selected_order=next(order for order in profile['orders'] if order['Order_ID']==active_order)
    st.markdown(f'''<div class="order-card"><div class="eyebrow">Selected order · {html.escape(active_order)}</div>
        <h3>{html.escape(selected_order['Product_Name'])}</h3>
        <div>{html.escape(selected_order['Colour'])} · Size {html.escape(selected_order['Size'])} · Qty {selected_order['Qty']}</div><br>
        <span class="status-pill">{html.escape(selected_order['Order_Status'])}</span>
        <span style="margin-left:10px;color:#746b66">Promised {str(selected_order['Promised_Delivery'])[:10]}</span></div>''',unsafe_allow_html=True)
    with st.expander(f"View all orders ({len(profile['orders'])})"):
        st.dataframe([{'Order':o['Order_ID'],'Product':o['Product_Name'],'Size':o['Size'],'Colour':o['Colour'],
            'Status':o['Order_Status'],'Promised delivery':str(o['Promised_Delivery'])[:10]} for o in profile['orders']],hide_index=True,width='stretch')
    if st.session_state.memory.get('order_id')!=active_order:
        st.session_state.memory={'order_id':active_order}

    conversations=agent.customer_conversations(cid)
    if conversations:
        conversation_labels={'Start a new chat':None}
        conversation_labels.update({c['updated_at'].replace('T',' ')[:16]+' · '+c['mode']+f' · Chat {index}':c['id']
                                    for index,c in enumerate(conversations,1)})
        current=st.session_state.conversation_id
        current_label=next((label for label,value in conversation_labels.items() if value==current),'Start a new chat')
        selected_label=st.selectbox('Select a previous chat',list(conversation_labels),index=list(conversation_labels).index(current_label))
        selected=conversation_labels[selected_label]
        if selected and selected!=current:
            st.session_state.conversation_id=selected;st.session_state.history=agent.messages(selected,cid)
            st.session_state.memory={};st.session_state.last=None;st.rerun()
        if selected is None and current in [c['id'] for c in conversations]:
            reset_customer_state(cid,True);st.rerun()
    st.divider()
    if not st.session_state.history:
        st.info('Try asking: “Where is my order?”, “Can I return this?”, or “Can I exchange this for another size?”')
    for message in st.session_state.history:
        render_message(message)

    last=st.session_state.last
    needs_condition=feedback_state()['phase'] in ['open','retry'] and last and last.get('status')=='needs_information' and last.get('intent') in ['return_request','exchange_size','exchange_color','fit_issue'] and not last.get('condition_ok')
    if needs_condition:
        st.session_state.condition_ok=st.checkbox('The item is unworn, unwashed, unaltered, unstained, and has its original tags.',value=st.session_state.condition_ok)
        if st.session_state.condition_ok and st.button('Continue eligibility check',type='primary'):
            submit_message('Yes, condition confirmed',cid)
    feedback=feedback_state()
    if feedback['phase']=='rating':
        st.caption('Chat closed · Was this helpful?')
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
                text='I’m sorry we haven’t resolved this. Would you like to talk to a support engineer? This prototype can save a simulated support request, but no one will be contacted.'
            agent.log_message(st.session_state.conversation_id,cid,'assistant',text)
            save_feedback(feedback)
            st.session_state.history=agent.messages(st.session_state.conversation_id,cid);st.rerun()
    elif feedback['phase']=='closed':
        st.caption('Chat closed. Thank you for your feedback.')
    elif feedback['phase']=='handoff':
        st.caption('Chat closed. You can request support below or start a new chat for a different issue.')
    if feedback['phase']=='handoff' and feedback.get('support_result'):
        last=feedback['support_result']
    show_action=feedback['phase']=='open' or feedback['phase']=='handoff'
    if last and last.get('pending') and show_action and last['as_of']==demo_date.isoformat():
        label={'return':'Initiate return','exchange':'Initiate exchange','cancellation':'Cancel order','escalation':'Request support engineer'}[last['pending']['kind']]
        c1,c2=st.columns([1,4])
        if c1.button(label,type='primary',width='stretch'):
            try:
                request=agent.confirm(last,st.session_state.conversation_id)
                message=f'Simulated support request {request} saved. No support engineer has been contacted.' if last['pending']['kind']=='escalation' else f'Request {request} created. Fulfilment remains simulated.'
                agent.log_message(st.session_state.conversation_id,cid,'assistant',message);agent.db.commit()
                st.session_state.history.append({'role':'assistant','content':message})
                if feedback['phase']=='handoff':
                    feedback['phase']='closed';save_feedback(feedback)
                st.session_state.last=None;st.rerun()
            except ValueError as error:st.error(str(error))
        c2.caption('Nothing is sent to a carrier, warehouse, payment provider, or support team.')
    prompt=st.chat_input('Type a message about your order…',disabled=feedback['phase'] not in ['open','retry'])
    if prompt:submit_message(prompt,cid)


def to_csv(rows):
    output=io.StringIO();writer=csv.DictWriter(output,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
    return output.getvalue()


def render_message(message,show_meta=False):
    role=message['role'];is_user=role=='user';avatar='You' if is_user else '✦'
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
        if rows:st.dataframe(rows,hide_index=True,width='stretch')
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
