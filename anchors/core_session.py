import streamlit as st

TEST_MODE = True

def init_session():
    defaults = {
        "auth_user": None,
        "role": None,
        "active_module": None
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

def handle_login():
    init_session()

    if TEST_MODE:
        st.session_state.auth_user = {"id": "test-user"}
        st.session_state.role = "admin"

    if not st.session_state.auth_user:
        st.title("🔐 Login")
        st.stop()

    if TEST_MODE:
        st.sidebar.warning("🧪 TEST MODE ENABLED")
