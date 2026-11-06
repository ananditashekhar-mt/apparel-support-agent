# Dataset and request workflow improvements

Integrated Deepti's richer dataset and response/UI changes with corrections.

## Dataset generation

Run `.venv/bin/python scripts/build_dataset.py` to rebuild 134 customers and 262 orders.
The immutable input is `data/source/orders.json` (the original 250 orders). Edit that
source when intentionally changing base orders. Generated orders and customers are
recreated, rather than appended. Customer IDs retain the app's original name/city
hash so existing saved conversations remain attached to their profiles.

Undelivered orders have zero delivered quantity. Partial deliveries have one of two
items delivered. Generated event timestamps never decrease along the lifecycle;
where source dates have only day precision, adjacent synthetic events can share a
timestamp. Shipment histories remain synthetic, rather than verified carrier scans.
Existing conversation messages and expected answers are preserved.

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

Run `.venv/bin/python -m unittest discover -s tests` for the existing suite plus
repeatability, quantity/timeline invariants, legacy identities, partial delivery,
damage, multi-turn cancellation, persistence, customer isolation and the Support form.

Run `.venv/bin/python evaluate.py --mode Demo --split test` for held-out intent
accuracy and escalation-label agreement. Agreement is reported only for explicit
Yes/No labels; other values are unscored. It is not verified escalation correctness.
The report also flags post-delivery reference cases linked to undelivered orders
and identical customer messages shared between training and test splits.

The Demo intent baseline remains 47/62 (75.8%). The audit flags 112 reference cases
for review and 28 distinct shared messages. These are review flags, not 112 proven
incorrect answers. Expected answers have not been rewritten automatically, and the
original split is retained for comparability. A separately curated holdout and
reviewed policy/tool labels are still needed for stronger quality claims.
Grounding, tone and open-ended conversation quality are not automatically graded.
No live OpenAI/Ollama run or Jev integration was performed in this change.
