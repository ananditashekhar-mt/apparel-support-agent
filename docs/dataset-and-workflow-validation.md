# Dataset and request workflow improvements

Integrated Deepti's richer dataset and response/UI changes with corrections.

## Dataset generation

Run `.venv/bin/python scripts/build_dataset.py` to rebuild the October–December 2026 India-only dataset:

- 200 synthetic customers across 35 cities/towns; 71 naturally repeated names with independent IDs, explicit gender, fictional email addresses and no real phone numbers.
- 600 orders: 50 single-order, 70 two-order, 50 four-order and 30 seven-order customer histories.
- 240 existing product variants; stable SKU-to-vendor mapping using three fictional vendors in `data/vendors.json`. Carriers are separate and fixed in `data/carriers.json`.
- 1,200 support conversations: 500 development, 100 showcase, 300 standard test, 200 challenge and 100 reserve.

`data/dataset_manifest.json` records the seed, version, dates and counts. The generator uses fixed input dictionaries and the product catalogue; it does not consume the old `data/source/orders.json`. It replaces generated outputs rather than appending. The earlier customer/order/conversation files are preserved in `data/archive/original/`.

Every order belongs to the same split as its customer and conversations. Customer gender and recipient apparel category agree except for explicitly marked gift purchases. Products, vendors, unit prices, totals, quantities and ordered shipment events are checked together. Pending deliveries have zero delivered quantity; partial deliveries have one of two items delivered. Dates and issue reports are coherent at each scenario's snapshot.

The 29 scenario variants cover every existing intent plus unknown requests. They test reporting on days 7/8, returns on days 29/30/31/40, stock availability, pre/post-shipment cancellation and handoffs. The challenge set additionally exercises identity checks, missing order context, instruction overrides and sequential size selection.

## Date-aware showcase

The sidebar offers 12 support groups, scenario variants and matching customer/order pairs. Load scenario selects its date and starts a fresh chat; Ask Tia this example submits the visible synthetic question. Eligible item-condition confirmation is supplied explicitly for those curated examples. Expected status and action labels are stored only in the evaluation file, not the public showcase file.

`dataset.order_as_of` hides future orders, filters future shipment events and removes delivery/issue facts until they occur. A historical order status is derived from its recorded events. After the snapshot date, the app preserves the last known facts rather than inventing delivery progress. The default simulation date is 31 December 2026. Changing dates starts a fresh chat.

The refreshed app uses `runtime_india_2026.sqlite` by default. Old chats/requests in `runtime.sqlite` remain untouched and separate from the new customer identities.

## Simulated customer and Support journey

1. Select an eligible confirmed order and request cancellation.
2. Confirm it to save a pending mock request.
3. Open Support, select the request, assign it, choose a status and save a reply.
4. Return to Customer to see the update in the order panel and saved transcript.
5. Ask for tracking: pending requests are acknowledged; completed cancellations
   appear as cancelled in the simulated state, including after reopening the database.

Updates are stored separately from source order data. No external system is called.
Existing requests without updates appear pending. Signed-in synthetic profiles can
see their requests across chats; anonymous requests remain isolated by chat.
Customer/Support/Admin still share the existing app; separate deployments and URLs
are outside this change. Existing access-code configuration remains in effect.

## Verification and evaluation limits

Run `.venv/bin/python -m unittest discover -s tests` for policy/workflow tests, generator repeatability, split and identity contracts, price/quantity/vendor checks, timestamp ordering, temporal visibility, and the scenario loader across all support groups.

Use `.venv/bin/python evaluate.py --mode Demo --split showcase` for the visible demo cases. The three evaluation splits (`test`, `challenge`, `reserve`) were scored after the refresh at the user’s request. They were not used to tune the agent after scoring; the reserve is now a recorded regression set. See [old/new comparison](dataset-comparison.md). The evaluator supports per-case dates, condition confirmation, customer/order ownership constraints and sequential follow-up turns. Expected outcomes are policy-authored, not produced by asking the agent for its own answer.

These are deterministic synthetic templates with separately worded partition banks, not an independently collected natural-language benchmark. Customer/order separation prevents identity overlap but does not imply language or scenario-family independence. Review labels and diversify authored conversations before using the results as a production quality claim. Old baseline results apply only to the archived dataset.

## Photo evidence and reopened conversations

Damaged, wrong-item and quality concerns offer a photo uploader in chat. Customers
can attach up to three JPG, PNG or WebP images (5 MB each, up to 20 megapixels).
Actual image contents are validated, and duplicates are not saved twice for the
same order/chat. Photos are stored as SQLite BLOBs with the conversation and order,
shown in the customer chat and Support transcript, and never treated as automated
proof of damage. A customer can request help without uploading a photo.

Past chats opens a read-only transcript with Reopen chat and Start a new chat.
Reopening requires either dissatisfaction with the earlier help or something
still pending, plus a written description. The reason and description are saved
in the same conversation; messages, attachments, proposals and requests remain.
A reopen begins a fresh feedback cycle. Finish chat closes the current conversation;
starting a new chat clears order and intent context without deleting prior history.

Storage follows the existing SQLite deployment: photos and chat history survive
reopening the database, but Streamlit hosting may reset local storage on restart
or redeployment. Production retention needs persistent storage. There is no model
vision assessment or automatic replacement approval in this implementation.


## End-of-chat CSAT

Finish chat and saved Support handoffs show a 1–5 customer satisfaction survey
with an optional comment and an explicit Submit feedback button. Selecting a
score alone does not submit it. Customers can skip without losing access to
reopening or new chats. Responses are stored in SQLite and shown in the Support
transcript. A reopened conversation gets a new survey cycle when it ends again;
reruns do not create duplicate responses. Existing low-score retry/handoff logic
uses the same form, so comments can also be captured on those feedback rounds.


## Back navigation and recent orders

Back controls return from chat to topics, from topics to order selection, from
issue descriptions to topics, and from reopening to the saved conversation. Past
chats remembers the current conversation so Back restores its context rather
than starting a new session. Navigation does not undo or delete saved requests.

The order picker initially shows the customer's three newest orders by purchase
date, with View all orders for older purchases. When a UI question is missing an
order (or references an unavailable order), the agent asks the customer to choose
from these cards rather than type an ID. Selection resumes the original question
and retains extracted intent/variant details. Only this profile's orders are shown.
CLI/reference evaluation keeps the existing text-only order-ID prompt.
