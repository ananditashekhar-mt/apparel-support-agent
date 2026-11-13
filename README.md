# Threadly · ISB Team 8

A friendly ecommerce-style prototype for **Threadly**, with **Tia** as its post-purchase care agent. It uses a compact Threadly monogram, a teal/coral retail palette, and small custom customer/Tia chat markers. Python and LangGraph coordinate the workflow; Streamlit provides separate customer, support, and admin interfaces. Demo, OpenAI and Ollama modes use the same code-enforced eligibility and action controls. No n8n dependency is needed for this version.

## Start here: Mac

### Simplest option for non-technical users

Unzip the folder and double-click **Start Threadly.command** on Mac or **Start Threadly.bat** on Windows. The launcher creates the environment, installs missing packages on the first run, and starts the app. Later launches skip setup. If macOS blocks the launcher, right-click it and choose **Open**. Python is the only prerequisite; if it is missing, the launcher opens the official download page.

The manual developer setup remains below for troubleshooting.

1. Install Python 3.11 or newer if it is not already installed.
2. Unzip this project. Open Terminal in the `apparel_agent` folder.
3. Run these commands, one line at a time:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Open the local address printed in Terminal, normally http://localhost:8501. Choose **Demo** to start without any API key. Keep Terminal running while using the app. Press Control+C in Terminal to stop.

For Windows, create the environment using `py -m venv .venv`, activate it with `.venv\Scripts\activate`, then run the same installation and launch commands.

## Try the chat

Use the default simulation date, 31 December 2026, or load a showcase scenario to select its October–December 2026 date automatically. Orders and shipment events after the selected date are hidden. Advancing beyond a recorded snapshot does not invent new carrier updates.

* Tracking: `Where is ORD-20002?`
* Delivery problem: `My order ORD-20002 is late.`
* Payment handoff: `Can you process my refund?`
* Return: use the delivered order shown in the sidebar. Tick the item-condition checkbox, then ask `I want to return ORD-xxxxx`.
* Exchange: ask `I want to exchange ORD-xxxxx` for a delivered order. When asked for the variant, reply `Size XL`. Availability comes from your catalog and may be zero.

Choose **Order to discuss** once, then ask natural questions such as “Where is my order?” without repeating the order ID in every message. Customer-facing examples never expose the selected order ID as internal agent context. Every fresh app/browser session starts with a blank conversation; it never opens an old chat automatically. Customers can explicitly reopen one from **Select a previous chat**. Empty abandoned chats are not listed. The item-condition confirmation appears only when it is relevant. The confirmation button creates a local mock request, never a real return, refund or shipment; inventory reservations remain in the shared local mock database.

The customer selector is a transparent stand-in for login because the supplied dataset has no usable email or account ID. It derives a stable synthetic customer ID from the synthetic name and city. A real-company version would require proper customer authentication, but that is outside this academic prototype.

## Customer and support interfaces

Choose the interface in the sidebar:

* **Customer** shows only the selected synthetic customer's orders and chat history. It keeps technical traces, policies, errors, and global usage out of the shopping experience.
* **Support** shows customer conversations, complete transcripts, and confirmed mock requests.
* **Admin** shows API usage/cost, database failures, the rotating diagnostic log, policies, and configuration status. Set separate `SUPPORT_ACCESS_CODE` and `ADMIN_ACCESS_CODE` values before deployment. When they are blank, the app explains that the corresponding local page is open only for prototype use.

Demo, OpenAI and Ollama conversations are stored in `runtime_india_2026.sqlite`. Messages are partitioned by customer ID and conversation ID. Support can inspect all records, while customer retrieval always includes that customer's ID in the query.

## Try different language models

The app supports three modes through the same guarded workflow:

* **Demo** uses the local rule-based language parser and requires no model.
* **OpenAI** uses an API model for intent extraction and response wording.
* **Ollama** uses a locally installed model through Ollama's OpenAI-compatible endpoint.

In all three modes, Python still controls order lookup, policy checks, eligibility, stock checks, confirmation and mock actions. This makes model comparisons meaningful because the business logic does not change.

### Connect OpenAI

1. Copy `.env.example` to `.env` in this folder.
2. Enter your API key after `OPENAI_API_KEY=` and an API model ID enabled in your account after `OPENAI_MODEL=`. No model or price is assumed from the earlier conversation.
3. Restart Streamlit. Choose **OpenAI** in the sidebar.

Do not share your `.env` file. Your API account is billed for calls. No API key is included in this project and no live OpenAI call was tested here. The adapter was tested using simulated responses and failures. OpenAI mode makes two model calls per message: structured understanding and a reply grounded in the retrieved policies and the code's decision. Each API call count and its combined input/output tokens are persisted.

Implementation references: [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs) and [LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api).

### Connect Ollama locally

1. Install and start Ollama.
2. Pull a model you want to test, for example `ollama pull qwen3:8b`.
3. Copy `.env.example` to `.env`, then set `OLLAMA_MODEL` to the exact installed model name.
4. Keep `OLLAMA_BASE_URL=http://localhost:11434/v1` and restart Streamlit.
5. Choose **Ollama** in the sidebar.

The model must support the structured JSON response used for intent extraction. If a smaller model is inconsistent, record that as an experiment result rather than changing the held-out expected answers. Ollama mode is intended for local experimentation. A hosted Streamlit app cannot reach Ollama running on your laptop through `localhost`.

Official references: [Ollama OpenAI compatibility](https://docs.ollama.com/api/openai-compatibility) and [Ollama quickstart](https://docs.ollama.com/quickstart).

## Share through GitHub and Streamlit

The project is publicly available in two forms:

* Source code and reproducibility materials: [GitHub repository](https://github.com/ananditashekhar-mt/apparel-support-agent)
* Working demonstration in Demo mode: [Tia by Threadly](https://tia-by-threadly.streamlit.app/)

The hosted default remains `APP_MODE=Demo` so the demonstration works without paid credentials or a local Ollama service. Add secrets only through the hosting platform's secret settings, never in the repository. Changes pushed to the GitHub `main` branch are redeployed by Streamlit Community Cloud.

Deployment reference: [Streamlit Community Cloud deployment](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy).

## What each component does

| Component | Job |
| --- | --- |
| Streamlit | Separate customer chat/history and support-operations views |
| LangGraph | Understand → retrieve → resolve → respond; passes conversation context between turns |
| OpenAI adapter | Classifies intent and extracts fields, then writes a reply using the authoritative decision and policy context |
| Policy retrieval | Uses intent metadata and lexical search over the nine policy rows; no embeddings or vector database are necessary for this small corpus |
| Order tool | Exact lookup of an order ID, never semantic search |
| Inventory tool | Looks up the precise SKU/size/colour and reserves the requested quantity when confirmed |
| Eligibility tool | Enforces delivery state, 30-day return/exchange window and condition confirmation in Python |
| SQLite | Stores conversations, messages, failures, usage, interaction results, confirmed requests and mock inventory reservations |

This is a constrained hybrid agent. The model understands variable language and generates responses; code controls eligibility, tools and writes. It is not a freely acting tool-selection agent. OpenAI replies may still contain wording errors: the expanded decision trace exposes the original code decision for review.

## Dataset preparation

The refreshed dataset contains **200 India-based customers, 600 orders, 240 product variants and 1,200 support conversations**. Orders, deliveries and shipment events cover October–December 2026. Policies retain the 16 supported intents, with an additional unknown fallback.

75% of customers have multiple orders: 50 have one, 70 have two, 50 have four and 30 have seven. Customer gender and recipient gender are explicit; purchases across men's/women's categories are marked as gifts. Names are fictional; 71 names are shared across 200 customers with common names weighted more heavily. Repeated names have different IDs, emails use `example.test`, and phone numbers are omitted. Thirty-five Indian cities/towns are represented. Three fixed fictional vendors are mapped by SKU; delivery partners are maintained separately in a fixed four-carrier list.

Regenerate with:

```bash
python scripts/build_dataset.py
```

The seeded generator replaces the generated JSON files deterministically. It does not edit policies, modify the runtime database or read the old source orders. Original customers/orders/conversations are preserved under `data/archive/original/`; the earlier raw orders remain in `data/source/orders.json`. See [dataset details](docs/dataset-and-workflow-validation.md).

## Showcase

In Customer view, use **Support use case → Scenario variant → Matching customer and order → Load scenario**. Loading selects the customer, order and scenario date, and starts a fresh chat. **Ask Tia this example** submits the visible example with the fixture's explicitly confirmed item condition when applicable. Expected outcomes are not read by the app or agent.

The 12 umbrella filters cover tracking, delay, delivered-not-received, incorrect items, damage/quality, missing quantities, returns, exchanges/fit, cancellations, refund enquiries, price adjustments and unrelated requests. Variants include 7/8-day reporting boundaries, 29/30/31/40-day returns, exchange availability and cancellation stages.

## Scope and limitations

Tracking, returns/exchanges, delivery exceptions, cancellation checks and human handoffs are implemented. Confirmed orders provide eligible cancellation examples. Recorded shipment events are synthetic; there is no live carrier, split-parcel tracking, verified proof of delivery or payment integration. Refund enquiries and price adjustments lead to human review. Photos can be attached but are not automatically assessed. Escalations create local mock cases; no external notification is sent.

The new dataset uses `runtime_india_2026.sqlite`, preserving the old `runtime.sqlite` separately so legacy chats and inventory do not attach to new identities. Requests and reservations remain local mock actions. Stop the app before removing the new database if you want a clean reset. Hosted local SQLite storage can reset on redeployment.

## Evaluate and verify

```bash
python -m unittest discover -s tests -v
python evaluate.py --split showcase
```

| Partition | Conversations | Purpose |
| --- | ---: | --- |
| train | 500 | Development |
| showcase | 100 | Curated demonstrations |
| test | 300 | Unseen standard evaluation |
| challenge | 200 | Unseen boundaries, Hinglish, identity checks, instruction overrides and size follow-ups |
| reserve | 100 | Unseen final reserve |

All five partitions have separate customers and orders and separately worded message banks. The challenge partition includes unknown order IDs, another customer's order, missing order context and multi-turn exchanges. These are synthetic template-based evaluation cases, not a production-language benchmark. Repeated scenario families are intentional; manual review of expected outcomes and more independently authored language are needed before strong quality claims.

The runner uses each scenario's `As_Of` date, active-order context, explicit condition confirmation and allowed order IDs. It executes follow-up messages sequentially when provided. It never passes expected outcomes to the agent. It reports intent accuracy, expected status/action agreement and escalation-label agreement; grounding, tone, evidence handling and request execution still require workflow tests or manual review.

The three evaluation partitions were subsequently run for the old/new comparison on 7 November 2026; they are now recorded regression sets. [Results and methodology](docs/dataset-comparison.md). Use `--split test`, `--split challenge` or `--split reserve` when ready to record a benchmark. Once used to guide fixes, a set becomes a regression set. The old 47/62 Demo result in `verification.json` belongs to the archived dataset and does not measure this one.

For model evaluation, configure `.env` and use `--mode OpenAI` (billed calls) or `--mode Ollama`. After the key was updated, a 600-case OpenAI evaluation using gpt-4.1-mini completed: 97.50% exact intent accuracy, 97.83% policy status/action agreement, zero API errors. That initial run exposed weak used/tagless-return handling. A subsequent condition-fact fix scored 17/17 on that category and 599/600 overall; fresh condition checks had 60/60 correct policy outcomes (59/60 exact intent labels). See the [initial live evaluation](docs/openai-new-dataset-evaluation.md) and [same-model comparison and fix](docs/openai-comparison-and-condition-fix.md). These are local synthetic-data tests; the deployed site remains unchanged.

## Cost analysis

No fixed model prices are assumed because rates vary by model and can change. Set `OPENAI_INPUT_USD_PER_M`, `OPENAI_OUTPUT_USD_PER_M`, and `USD_INR_RATE` in `.env` using current published rates. If a model's rates are I and O dollars per million input and output tokens, its cost is:

`(total_input_tokens × I + total_output_tokens × O) / 1,000,000`

The support dashboard totals API requests, input tokens, output tokens, estimated USD, and approximate INR. There are no embedding or vector-database API charges in this implementation. Demo mode and locally run Ollama have no per-call model charge. These values are estimates, not an invoice.

## Files you may edit

* `agent.py`: understanding, policy retrieval, tools, eligibility and confirmed mock actions.
* `app.py`: chat UI.
* `data/policies.json`: authoritative text supplied to the model. If changing policy windows, also update their enforcement in `agent.py` and the boundary tests.
* `evaluate.py`: held-out evaluation runner.
* `proactive.py`: scheduled event preview.
* `tests/test_agent.py`: workflow verification.

The dependencies are pinned to the versions used to verify this package. Network access is needed to install them and for OpenAI mode. Ollama mode requires a running local or remote Ollama endpoint.

### Local conversational-flow update

Tia greets the selected synthetic customer by name, introduces herself on the next line, then separates the explanation with a blank line. Customer replies do not use em dashes. Expired return/exchange requests check the delivery date before requesting condition confirmation and explain only the 30-day window. This explanation is rendered from the code decision rather than the model rewrite.

For this outcome, a separate closing message is followed by a 1–5 star rating with chat input closed. A rating of 4 or 5 ends the flow. The first rating below 4 reopens the chat for one further response and rating. A second rating below 4 offers a support engineer and cannot restart the automated loop. The round count and closure state persist in SQLite per conversation, including when a saved chat is reopened. Support requests remain local simulations and contact nobody. Starting a new chat creates a separate conversation.

The 26 automated tests include isolated UI-flow tests for the star-rating threshold, two-round cap, persisted closure, greeting layout and mock support request. No fresh live-model quality score is claimed for this revision. Earlier accuracy figures do not measure the updated prompts and workflow.

### Optional Jev shadow experiment

Jev can classify intent and analyze written CSAT feedback alongside the existing workflow. It never changes extracted order/size/colour fields, replies, eligibility, actions, ratings, closure, retry limits or handoffs. This is an experiment, not a replacement for the current parser.

To enable locally, set these in `.env` and restart the app:

```dotenv
JEV_SHADOW_ENABLED=true
TYPESAFE_API_KEY=your_private_key
JEV_MODEL=jev-latest
```

The default is disabled and makes no TypeSafe requests. When enabled, each message sends the latest message, up to eight history entries and prior parsed context to TypeSafe. Each new CSAT submission with a nonempty comment sends its rating and comment; empty comments and duplicate submissions make no extra request. Use synthetic data for initial evaluation. The fixed HTTPS endpoint uses a five-second timeout and no application retries. Provider errors or malformed responses are recorded without replacing the existing customer decision. Requests run synchronously, so shadow mode adds latency. Keep it off for ordinary demos until configured.

Inspect **Admin → Diagnostic log → Jev shadow decisions**, or download the JSON results. Records include resolved model, answer probabilities/confidence, reported token usage, request latency, baseline intent/agreement or CSAT submission ID/rating, and sanitized failure types. Jev token usage is separate from the existing OpenAI/Ollama cost totals; monetary savings are not calculated. Raw customer inputs and API keys are not copied into shadow records. Records live in the existing local SQLite database.

CSAT questions identify the main expressed reason, an explicit request for a person and an explicitly unresolved issue. This can expose a high star rating with an unresolved complaint and distinguish policy dissatisfaction from unclear communication. These are review signals only: a predicted label does not prove a cause, authorize a handoff or override a customer's rating. The existing first-low-rating retry, second-low-rating handoff offer, and 4–5-star closure remain controlled by code.

Evaluate intent against independently labeled examples, including multi-turn exchanges, Hinglish and ambiguous requests. Agreement with the current parser is a comparison, not accuracy. Independently label CSAT comments before measuring unresolved-issue and human-request recall. Keep regression cases distinct from fresh evaluation data; compare total latency and actual billed costs before promoting any decision to live routing. No live Jev quality or performance result is claimed. Integration follows the [TypeSafe HTTP API](https://docs.typesafe.ai/api/system-one) and [Choice schema](https://docs.typesafe.ai/primitives/choice).

### Gemini and GroqCloud

The Assistant selector also supports Gemini and Groq. Double-click `Configure Models.command` to enter or replace provider keys privately. Press Enter to skip any key you do not want to change. Gemini uses `GEMINI_API_KEY` and `GEMINI_MODEL`; Groq uses `GROQ_API_KEY` and `GROQ_MODEL`. Suggested starting models are `gemini-2.5-flash` and `openai/gpt-oss-20b`. Availability and free quotas depend on your account. These providers use their OpenAI-compatible Chat Completions endpoints, including JSON schema extraction. Business rules remain in Python. Hosted adapters are tested with simulated responses; live use requires valid keys.

Double-click `Start App.command` to launch the app, then choose a provider under **Demo settings → Assistant**. Restart after saving new keys. Keep Demo selected until credentials are configured.

### Free-form conversations and service views

Customers can type without selecting an order. Tia answers general return, exchange and delivery-policy questions from the supplied policies, asks a natural follow-up for greetings or vague requests, and asks for an order only when a specific issue needs one. Unknown information is stated explicitly. Unrelated questions receive a scope explanation; invoice requests can still be offered to Support. General questions retain the selected order and previous order intent so the customer can resume it. General answers do not start the closure/rating prompt.

Run `python evaluate.py --split free_form` for the additional response, routing and context regression dataset in `data/free_form_conversations.json`. It is separate from the frozen order benchmark and does not change its historical scores. No new live-provider accuracy claim is made.

Support links transcripts to requests, resolution statuses and order details, including conversations without a service request. Request updates persist the status, assignee and customer-visible reply, append that reply to the customer transcript and update the conversation timestamp. Completed mock cancellations appear in subsequent tracking and order detail views. Admin includes a service overview alongside usage, errors, configuration and diagnostics. Updates remain mock actions; no real payment, shipment or external notification is performed.

Generic order-help requests, including short replies such as “with an order,” ask what happened before requesting order context. Hosted intent extraction uses recent dialogue to distinguish incomplete support requests from unrelated topics. The free-form regression set checks intermediate routing as well as final responses.


### Assistant controls and reply feedback

The expanded Assistant settings panel always exposes Demo, OpenAI, Gemini, Groq and Ollama and identifies the active selection. Provider keys and models still come from private environment variables or Streamlit Secrets; selecting a provider does not configure its credentials. The older ALLOW_MODE_SWITCH flag no longer hides the selector. Synthetic-order notices describe the data, independently of the selected assistant.

Desktop chat fills the available width and its transcript adapts to viewport height. Mobile remains a separate 390 px preview. Submitting a message immediately shows it and Thinking…; Loading… is reserved for UI work. A quiet, short reply tone can be muted with Reply sound. Browser audio requires an initial interaction, and old replies are not replayed when navigating.

Support and Admin retain separate access codes. The owner can find SUPPORT_ACCESS_CODE and ADMIN_ACCESS_CODE under Streamlit → Manage app → Settings → Secrets. An unlocked role stays available for the browser session, with a Lock button; changing the configured code invalidates that unlock. No code or API key is included in the repository.

Chat transitions replace the previous transcript contents as a single block and hide stale Streamlit elements during processing. Preview tools live in the sidebar; desktop toolbar actions and order selection buttons keep compact widths.


### Context-aware model replies and random showcase customers

OpenAI, Groq, Gemini and Ollama now use model understanding and response generation for conversational turns as well as order requests. Both stages receive recent conversation history. Greetings and small talk no longer bypass the response model. Demo remains deterministic. Code continues to enforce eligibility, ownership, confirmation and mock actions; order-picker instructions and expired-window responses retain the authoritative wording. Model usage is recorded for these calls.

Selecting a showcase support use case immediately loads a random matching customer, scenario order and simulation date into a fresh chat. Changing the scenario variant does the same within that variant. Try another customer selects a different matching customer where possible. Normal reruns keep the selected scenario stable. Manual matching-customer selection also loads automatically. Selecting a scenario alone does not send a customer message or make a model request.
