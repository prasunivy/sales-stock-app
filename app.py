import sys
import os
import streamlit as st

# Force project root into Python path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from anchors.core_session import handle_login
from anchors.core_router import route_module

st.set_page_config(
    page_title="Ivy Pharmaceuticals",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
thead th {
    position: sticky;
    top: 0;
    background-color: #fafafa;
    z-index: 2;
}
tbody td:first-child, thead th:first-child {
    position: sticky;
    left: 0;
    background-color: #fafafa;
    z-index: 1;
}
</style>
""", unsafe_allow_html=True)

handle_login()
route_module()
