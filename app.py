import sys
import os
import streamlit as st

# Force project root into Python path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from anchors.core_session import handle_login
from anchors.core_router import route_module
from anchors.ivy_styles import apply_styles

st.set_page_config(
    page_title="Ivy Pharmaceuticals",
    layout="wide",
    initial_sidebar_state="collapsed"
)

apply_styles()

handle_login()
route_module()
