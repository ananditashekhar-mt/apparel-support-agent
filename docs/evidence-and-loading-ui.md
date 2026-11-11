# Photo evidence and loading feedback — 11 November 2026

The photo form previously appeared whenever a chat had a damage, wrong-item or
quality intent, even when the policy decision blocked the request because the
order had not been delivered. Rendering now requires the current decision to
offer Support escalation, the same simulation date, an order owned by the
selected customer, and a confirmed delivery in that date's order projection.
Intent or stale conversation memory alone cannot expose the form.

UI regressions check that delivered damage still offers uploads, while
in-transit, shipped, delayed and cancelled orders do not. Another test moves
the simulation date before a recorded delivery and verifies uploads stay
hidden. These tests run the actual customer interface and deterministic policy
path; no new LLM classification change is involved.

A circular, non-blocking Loading indicator appears during Streamlit's initial
and running script states, covering reruns caused by navigation, reads, saves
and replies. It disappears when the run completes, supports reduced-motion
preferences, and leaves the toolbar, sidebar and composer accessible. The
existing contextual request spinner remains. Before the app's first HTML/CSS
arrives, and during file-transfer progress, Streamlit's native indicators apply.
