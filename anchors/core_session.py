import streamlit as st

TEST_MODE = False

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
    Shows login form if not authenticated
    """
    init_session()
    
    # Check if already logged in
    if st.session_state.auth_user:
        return  # User is authenticated, continue to app
    
    # Show login screen
    st.title("🔐 Ivy Pharmaceuticals")
    st.write("### Please Login")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login", type="primary")
        
        if submit:
            if not username or not password:
                st.error("Please enter username and password")
            else:
                try:
                    from anchors.supabase_client import supabase, safe_exec
                    
                    # Convert username to email
                    user_check = safe_exec(
                        supabase.table("users")
                        .select("id, is_active, role")
                        .eq("username", username)
                        .limit(1)
                    )
                    
                    if not user_check or not user_check[0]["is_active"]:
                        st.error("❌ Invalid or inactive user")
                        st.stop()
                    
                    email = f"{username}@internal.local"
                    
                    # Authenticate with Supabase
                    auth_response = supabase.auth.sign_in_with_password({
                        "email": email,
                        "password": password
                    })
                    
                    # Store in session
                    st.session_state.auth_user = auth_response.user
                    st.session_state.role = user_check[0]["role"]
                    
                    st.success(f"✅ Welcome, {username}!")
                    st.rerun()
                
                except Exception as e:
                    st.error(f"❌ Login failed: {str(e)}")
    
    # Stop execution until logged in
    st.stop()
