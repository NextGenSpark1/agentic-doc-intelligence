import streamlit as st

st.set_page_config(
    page_title="Investigation Intelligence",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from utils.styles import inject_styles  # noqa: E402

inject_styles("Cases")
st.switch_page("pages/1_Cases.py")
