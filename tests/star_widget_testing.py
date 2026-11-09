"""Adapt AppTest's list-only ButtonGroup serializer for native st.feedback."""
from unittest.mock import patch
from streamlit.testing.v1.element_tree import ButtonGroup

def feedback_indices(widget):
    try:value=widget.value
    except KeyError:return [] # AppTest can retain a removed form for one rerun.
    return [] if value is None else [value] if isinstance(value,int) else value

def enable_star_testing(case):
    adapter=patch.object(ButtonGroup,'indices',property(feedback_indices))
    adapter.start()
    case.addCleanup(adapter.stop)

def set_stars(app,score):
    app.get('button_group')[0].set_value([] if score is None else [score-1])
