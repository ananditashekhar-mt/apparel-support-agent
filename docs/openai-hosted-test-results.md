# Hosted OpenAI test results

Manual acceptance tests. Results below are assessed from responses supplied by the tester; they are not independently verified hosted runs.

| Test ID | Scenario | Customer message | Expected result | Actual result | Verdict | Support conversation ID |
| --- | --- | --- | --- | --- | --- | --- |
| TC-01 | Order tracking: Rohan, Delhi — ORD-10003 | Where is my order? | Report the recorded delayed status, carrier, tracking ID and promised date without inventing a live update. | Delayed; Xpressbees; TRK39372360; promised July 31, 2026. Explicitly states live carrier scans are unavailable. Matches the repository order record. | Pass | f84fc1c8-ea65-405b-ab38-8f1dc94fd431 |

| TC-02 | Follow-up requesting an exact arrival date for ORD-10003 | Exactly when will it arrive? | Acknowledge that an arrival estimate is unavailable without carrier data; do not invent a date. | States that no carrier scan or delivery confirmation is available and cannot provide an estimated delivery date. Offers a Request support engineer action. Action creation has not yet been tested. | Pass | f84fc1c8-ea65-405b-ab38-8f1dc94fd431 |

Exact OpenAI model, deployed code revision and simulation date have not yet been recorded for this run.
