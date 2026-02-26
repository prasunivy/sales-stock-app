import streamlit as st

from modules.statement.statement_main import run_statement
from modules.ops.ops_main import run_ops
from modules.dcr.dcr_main import run_dcr
from modules.dcr.doctor_fetch import run_doctor_fetch
from modules.pob.pob_main import run_pob


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

    if st.sidebar.button("📋 POB / Statement / Cr Nt"):
        st.session_state.active_module = "POB"
        st.rerun()

    # ── Route to active module ──────────────────────────────

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
        run_pob()

    else:
        st.title("🏠 Home")
        st.write("👈 Click a module from the sidebar")
