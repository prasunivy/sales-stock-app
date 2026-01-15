import streamlit as st

from anchors.core_session import handle_login
from anchors.core_router import route_module

st.set_page_config(
    page_title="Ivy Pharmaceuticals (TEST)",
    layout="wide",
    initial_sidebar_state="expanded"
)

handle_login()
route_module()
