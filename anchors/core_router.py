import streamlit as st

from modules.statement.statement_main import run_statement
from modules.ops.ops_main import run_ops
from modules.dcr.dcr_main import run_dcr             
from modules.dcr.doctor_fetch import run_doctor_fetch

def route_module():
    st.sidebar.subheader("📂 Modules")

    if st.sidebar.button("📦 Sales & Stock Statement"):
        st.session_state.active_module = "STATEMENT"
        st.rerun()

    if st.sidebar.button("📥 Order / Purchase / Sales / Payment"):
        st.session_state.active_module = "OPS"
        st.rerun()

    active = st.session_state.get("active_module")

    if active == "STATEMENT":
        run_statement()

    elif active == "OPS":
        run_ops()

    else:
        st.title("🏠 Home")
        st.write("👈 Click a module from the sidebar")
