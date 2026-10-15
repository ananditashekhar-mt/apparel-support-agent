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

Use the default demo date, 17 September 2026. This makes eligibility relative to the synthetic workbook dates, rather than today.

* Tracking: `Where is ORD-10003?`
* Delivery problem: `My order ORD-10003 is late.`
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

Demo, OpenAI and Ollama conversations are stored in `runtime.sqlite`. Messages are partitioned by customer ID and conversation ID. Support can inspect all records, while customer retrieval always includes that customer's ID in the query.

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

The project includes JSON exports of all six useful workbook tabs: nine policies, 240 product variants, 250 orders, 400 conversations, 16 intents and seven rubric dimensions. Expected answers are **not** read by the runtime agent.

Some workbook headers do not match their values. Preparation renamed fields without modifying the uploaded workbook:

| Sheet | Original heading | Prepared heading |
| --- | --- | --- |
| Orders | Customer_Last_Name | Customer_Name_Synthetic |
| Orders | Customer_Email | City |
| Support_Conversations | Customer_First_Name | Split |
| Support_Conversations | Customer_Last_Name | Order_ID |
| Support_Conversations | Customer_Email | SKU |

Blank columns were removed. Dates remain ISO strings. The synthetic conversations can contradict the linked order status, and expected answers sometimes imply carrier information absent from the workbook. The prototype follows the actual available records and identifies missing facts.

## Scope and limitations

Tracking, returns/exchanges, delivery exceptions, cancellation checks and human handoffs are implemented. The dataset contains no clearly pre-shipment confirmed orders, so cancellation creation has no eligible example in the supplied orders. No refund or financial action is implemented.

Carrier scans, split shipments, proof of delivery and refund status are absent. Those queries cannot be fully resolved and propose human review. Photo verification is not implemented; damage/incorrect-item cases request evidence and human review. An escalation creates a mock case locally, not a notification to a real person.

Orders are fixed mock records. Requests do not change their fulfilment status. Chat transcripts persist in SQLite; reasoning memory is not yet reconstructed when an old transcript is reopened. This is an academic demonstration without real customer authentication or external commerce integrations. Use only the supplied synthetic data. A scheduled proactive-update preview is included in `proactive.py`; delivery notifications are previews only.

To reset mock reservations and requests, stop the app and delete `runtime.sqlite`, then restart. Do not delete that file while the app is running.

## Evaluate and verify

```bash
python -m unittest discover -s tests -v
python evaluate.py --split test
```

The evaluation runner preserves the supplied splits. It does not pass expected answers or labels to the agent. It provides the explicitly mapped order ID as initial customer context. It does not assume item condition, which must be confirmed separately.

Twenty-three workflow tests cover the original business rules plus active-order context, question/reply ordering, return-condition continuation, customer-history isolation, order-ownership checks, provider adapters, failure logging, and token or cost persistence. The held-out **Demo** baseline identified the exact intent in 47 of 62 test conversations, **75.8%**. This measures the rule classifier, not live LLM quality or end-to-end resolution. No test-set prompt tuning was performed after this baseline. `verification.json` records the earlier baseline checks.

For OpenAI evaluation, run `python evaluate.py --mode OpenAI --split test` after configuring `.env`. This makes billed API calls. For a local model, run `python evaluate.py --mode Ollama --split test`. The output contains actual responses, expected actions and empty rubric-score fields for manual review. Run a small validation subset before the 62 held-out test conversations, and run multi-turn cases separately in the UI because the evaluation runner tests single-turn scenarios only.

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
