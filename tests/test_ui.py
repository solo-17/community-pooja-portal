"""Streamlit App UI Smoke Test."""

from streamlit.testing.v1 import AppTest


def test_app_renders_without_exception():
    """Verify that app.py loads, renders the header, tabs, and slots without unhandled exceptions."""
    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()

    # Verify no exception elements were displayed
    assert len(at.exception) == 0
    # Check that 4 tabs rendered
    assert len(at.tabs) >= 4
