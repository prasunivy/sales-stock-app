"""
Ivy Pharmaceuticals — AI Business Assistant
Powered by Claude API
Place at: modules/ai/ai_assistant.py
"""

import streamlit as st
import json
import time
import requests
from datetime import datetime, date
from calendar import monthrange
from anchors.supabase_client import admin_supabase, safe_exec


MODEL      = "claude-sonnet-4-5"
MAX_TOKENS = 1000
LIMIT_ADMIN = 300
LIMIT_USER  = 200

SYSTEM_PROMPT = """You are the Ivy Pharmaceuticals business intelligence assistant.
Answer questions about sales, payments, stock, invoices, credit notes, and doctors.
Use ₹ for amounts. Be concise and accurate. Only state what the data shows."""


# ── Usage tracking ────────────────────────────────────────────────
def _get_usage(user_id):
    now = datetime.utcnow()
    try:
        row = safe_exec(
            admin_supabase.table("ai_usage")
            .select("question_count")
            .eq("user_id", user_id)
            .eq("month", now.month)
            .eq("year", now.year)
            .limit(1)
        )
        return int(row[0]["question_count"]) if row else 0
    except Exception:
        return 0


def _increment_usage(user_id):
    now = datetime.utcnow()
    try:
        existing = safe_exec(
            admin_supabase.table("ai_usage")
            .select("id, question_count")
            .eq("user_id", user_id)
            .eq("month", now.month)
            .eq("year", now.year)
            .limit(1)
        )
        if existing:
            admin_supabase.table("ai_usage").update({
                "question_count": existing[0]["question_count"] + 1,
                "updated_at": now.isoformat()
            }).eq("id", existing[0]["id"]).execute()
        else:
            admin_supabase.table("ai_usage").insert({
                "user_id": user_id,
                "month": now.month,
                "year": now.year,
                "question_count": 1
            }).execute()
    except Exception:
        pass


# ── Fetch DB context ──────────────────────────────────────────────
def _fetch_context(question, role, user_id):
    q = question.lower()
    parts = []
    today = date.today()

    # Date range
    month_map = {
        "january":1,"february":2,"march":3,"april":4,"may":5,"june":6,
        "july":7,"august":8,"september":9,"october":10,"november":11,"december":12,
        "jan":1,"feb":2,"mar":3,"apr":4,"jun":6,"jul":7,
        "aug":8,"sep":9,"oct":10,"nov":11,"dec":12
    }
    detected_month = next((v for k, v in month_map.items() if k in q), None)
    yr = today.year
    if detected_month:
        from_d = date(yr, detected_month, 1)
        _, ld = monthrange(yr, detected_month)
        to_d = date(yr, detected_month, ld)
    elif "this month" in q or "current month" in q:
        from_d = date(yr, today.month, 1)
        _, ld = monthrange(yr, today.month)
        to_d = date(yr, today.month, ld)
    elif "last month" in q:
        m = today.month - 1 or 12
        y = yr if today.month > 1 else yr - 1
        from_d = date(y, m, 1)
        _, ld = monthrange(y, m)
        to_d = date(y, m, ld)
    else:
        from_d = date(yr, 1, 1)
        to_d = date(yr, 12, 31)

    parts.append(f"Date range: {from_d} to {to_d}. Today: {today}")

    # Payments
    if any(w in q for w in ["payment","paid","receipt","received","collection"]):
        try:
            rows = safe_exec(
                admin_supabase.table("ops_documents")
                .select("ops_no,ops_date,ops_type,from_entity_type,from_entity_id,"
                        "to_entity_type,to_entity_id,invoice_total,narration,payment_mode")
                .in_("ops_type", ["PAYMENT","RECEIPT"])
                .eq("is_deleted", False)
                .gte("ops_date", from_d.isoformat())
                .lte("ops_date", to_d.isoformat())
                .order("ops_date", desc=True)
                .limit(30)
            ) or []
            if rows:
                total = sum(float(r.get("invoice_total") or 0) for r in rows)
                parts.append(f"PAYMENTS ({len(rows)} records, total ₹{total:,.2f}):\n" +
                              json.dumps(rows, default=str))
        except Exception as e:
            parts.append(f"Payment fetch error: {e}")

    # Invoices
    if any(w in q for w in ["invoice","sale","outstanding","due","unpaid","billing"]):
        try:
            rows = safe_exec(
                admin_supabase.table("ops_documents")
                .select("ops_no,ops_date,stock_as,from_entity_type,from_entity_id,"
                        "to_entity_type,to_entity_id,invoice_total,outstanding_balance,"
                        "payment_status,reference_no")
                .eq("stock_as", "normal")
                .eq("is_deleted", False)
                .gte("ops_date", from_d.isoformat())
                .lte("ops_date", to_d.isoformat())
                .order("ops_date", desc=True)
                .limit(30)
            ) or []
            if rows:
                total = sum(float(r.get("invoice_total") or 0) for r in rows)
                parts.append(f"INVOICES ({len(rows)} records, total ₹{total:,.2f}):\n" +
                              json.dumps(rows, default=str))
        except Exception as e:
            parts.append(f"Invoice fetch error: {e}")

    # Stock
    if any(w in q for w in ["stock","inventory","closing","qty","quantity"]):
        try:
            rows = safe_exec(
                admin_supabase.table("stock_ledger")
                .select("product_id,entity_type,entity_id,txn_date,qty_in,qty_out,closing_qty,narration")
                .gte("txn_date", from_d.isoformat())
                .lte("txn_date", to_d.isoformat())
                .order("txn_date", desc=True)
                .limit(40)
            ) or []
            if rows:
                parts.append(f"STOCK LEDGER ({len(rows)} records):\n" +
                              json.dumps(rows, default=str))
        except Exception as e:
            parts.append(f"Stock fetch error: {e}")

    # Credit notes
    if any(w in q for w in ["credit note","cn","credit","return"]):
        try:
            rows = safe_exec(
                admin_supabase.table("ops_documents")
                .select("ops_no,ops_date,stock_as,from_entity_type,from_entity_id,"
                        "to_entity_type,to_entity_id,invoice_total,reference_no")
                .eq("stock_as", "credit_note")
                .eq("is_deleted", False)
                .gte("ops_date", from_d.isoformat())
                .lte("ops_date", to_d.isoformat())
                .limit(20)
            ) or []
            if rows:
                total = sum(float(r.get("invoice_total") or 0) for r in rows)
                parts.append(f"CREDIT NOTES ({len(rows)} records, total ₹{total:,.2f}):\n" +
                              json.dumps(rows, default=str))
        except Exception as e:
            parts.append(f"CN fetch error: {e}")

    # General fallback
    if len(parts) <= 1:
        try:
            rows = safe_exec(
                admin_supabase.table("ops_documents")
                .select("ops_no,ops_date,ops_type,stock_as,invoice_total,payment_status")
                .eq("is_deleted", False)
                .gte("ops_date", from_d.isoformat())
                .lte("ops_date", to_d.isoformat())
                .order("ops_date", desc=True)
                .limit(20)
            ) or []
            if rows:
                parts.append(f"RECENT ACTIVITY ({len(rows)} records):\n" +
                              json.dumps(rows, default=str))
        except Exception as e:
            parts.append(f"General fetch error: {e}")

    return "\n\n".join(parts)


# ── Call Claude API ───────────────────────────────────────────────
def _call_claude(question, context):
    try:
        api_key = st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        return "⚠️ ANTHROPIC_API_KEY not found in Streamlit secrets."

    user_msg = f"Data from database:\n{context}\n\nQuestion: {question}"

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": MODEL,
            "max_tokens": MAX_TOKENS,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_msg}],
        },
        timeout=45,
    )

    if resp.status_code == 200:
        data = resp.json()
        return data["content"][0]["text"]
    else:
        return f"⚠️ API error {resp.status_code}: {resp.text[:500]}"


# ── Main UI ───────────────────────────────────────────────────────
def run_ai_assistant():
    user    = st.session_state.get("auth_user")
    role    = st.session_state.get("role", "user")
    user_id = user.id if user else None

    if "ai_chat" not in st.session_state:
        st.session_state.ai_chat = []  # list of {"q": ..., "a": ...}

    st.markdown("### 🤖 Ivy Assistant")

    limit     = LIMIT_ADMIN if role == "admin" else LIMIT_USER
    used      = _get_usage(user_id) if user_id else 0
    remaining = max(0, limit - used)
    st.caption(f"Ask anything about sales, payments, stock, or doctors. "
               f"**{remaining}** questions remaining this month.")

    if remaining == 0:
        st.warning(f"Monthly limit of {limit} questions reached. Resets on the 1st.")
        return

    # Show conversation
    for turn in st.session_state.ai_chat:
        with st.chat_message("user"):
            st.write(turn["q"])
        with st.chat_message("assistant"):
            st.write(turn["a"])

    # Process pending suggestion click
    if "_ai_pending" in st.session_state:
        pending = st.session_state.pop("_ai_pending")
        with st.spinner("Thinking..."):
            try:
                ctx = _fetch_context(pending, role, user_id)
                ans = _call_claude(pending, ctx)
            except Exception as e:
                ans = f"⚠️ {e}"
        st.session_state.ai_chat.append({"q": pending, "a": ans})
        if user_id and not ans.startswith("⚠️"):
            _increment_usage(user_id)
        st.rerun()

    # Chat input
    question = st.chat_input("Ask about your sales, payments, stock...")
    if question and question.strip():
        with st.spinner("Thinking..."):
            try:
                ctx = _fetch_context(question.strip(), role, user_id)
                ans = _call_claude(question.strip(), ctx)
            except Exception as e:
                ans = f"⚠️ {e}"
        st.session_state.ai_chat.append({"q": question.strip(), "a": ans})
        if user_id and not ans.startswith("⚠️"):
            _increment_usage(user_id)
        st.rerun()

    # Clear button
    if st.session_state.ai_chat:
        if st.button("🗑 Clear conversation", key="ai_clear"):
            st.session_state.ai_chat = []
            st.rerun()
