import streamlit as st

TEST_MODE = True

def init_session():
    """
    Initialize all session state keys
    """
    defaults = {
        "auth_user": None,
        "role": None,
        "active_module": None,
        # Add keys that other modules need
        "statement_id": None,
        "product_index": None,
        "statement_year": None,
        "statement_month": None,
        "selected_stockist_id": None,
        "engine_stage": None,
        "admin_section": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def handle_login():
    """
    Handle authentication
    TEST_MODE: auto-login as admin
    """
    init_session()
    
    if TEST_MODE:
        # Auto-login in test mode
        st.session_state.auth_user = {"id": "00000000-0000-0000-0000-000000000001"}
        st.session_state.role = "admin"
    
    if not st.session_state.auth_user:
        st.title("🔐 Login")
        st.write("Authentication required")
        st.stop()
    
    if TEST_MODE:
        st.sidebar.warning("🧪 TEST MODE ENABLED")
