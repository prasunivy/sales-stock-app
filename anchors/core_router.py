import streamlit as st

from modules.statement.statement_main import run_statement
from modules.ops.ops_main import run_ops
from modules.dcr.dcr_main import run_dcr
from modules.dcr.doctor_fetch import run_doctor_fetch

# Try to import POB and catch any error so we can see it
try:
    from modules.pob.pob_main import run_pob
    POB_AVAILABLE = True
    POB_ERROR = None
except Exception as e:
    POB_AVAILABLE = False
    POB_ERROR = str(e)


def route_module():
    st.sidebar.subheader("📂 Modules")

    if st.sidebar.button("📦 Sales & Stock Statement"):
        st.session_state.active_module = "STATEMENT"
        st.rerun()

    if st.sidebar.button("📥 Order / Purchase / Sales / Payment"):
        st.session_state.active_module = "OPS"
        st.rerun()

    if st.sidebar.button("📞 Daily Call Report"):
        st.session_state.active_module = "DCR"
        st.rerun()

    if st.sidebar.button("🔍 Doctor Fetch"):
        st.session_state.active_module = "DOCTOR_FETCH"
        st.rerun()

    # Show POB button or error
    if POB_AVAILABLE:
        if st.sidebar.button("📋 POB / Statement / Cr Nt"):
            st.session_state.active_module = "POB"
            st.rerun()
    else:
        st.sidebar.error(f"POB Error: {POB_ERROR}")

    # Route
    active = st.session_state.get("active_module")

    if active == "STATEMENT":
        run_statement()
    elif active == "OPS":
        run_ops()
    elif active == "DCR":
        run_dcr()
    elif active == "DOCTOR_FETCH":
        run_doctor_fetch()
    elif active == "POB":
        if POB_AVAILABLE:
            run_pob()
        else:
            st.error(f"POB module failed to load: {POB_ERROR}")
    else:
        st.title("🏠 Home")
        st.write("👈 Click a module from the sidebar")
