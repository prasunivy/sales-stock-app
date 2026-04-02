"""
Ivy Pharmaceuticals — AI Business Assistant
Powered by Claude API (claude-sonnet-4-20250514)

Place this file at: modules/ai/ai_assistant.py
"""

import streamlit as st
import json
import re
from datetime import datetime, date
from calendar import monthrange
from anchors.supabase_client import admin_supabase, safe_exec


# ─────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────
MODEL          = "claude-sonnet-4-5"
MAX_TOKENS     = 1000
MONTHLY_LIMIT_ADMIN = 300
MONTHLY_LIMIT_USER  = 200

SYSTEM_PROMPT = """You are the Ivy Pharmaceuticals business intelligence assistant.
You help the sales and admin team understand their data — payments, invoices, credit notes, stock movements, DCR reports, tour programmes, and doctor visits.

YOUR ROLE:
- Answer questions about the business data in plain, friendly language
- Always show numbers clearly (use ₹ for amounts, commas for thousands)
- Keep answers concise but complete
- If data is ambiguous, say so and ask a clarifying question
- Never invent or guess numbers — only state what the data shows

DATABASE SCHEMA (Supabase / PostgreSQL):

TABLE: ops_documents
  id uuid PK | ops_no text | ops_date date | ops_type text | stock_as text
  direction text | from_entity_type text | from_entity_id uuid
  to_entity_type text | to_entity_id uuid
  invoice_total numeric | paid_amount numeric | outstanding_balance numeric
  payment_status text | allocation_status text | is_deleted boolean
  narration text | reference_no text | payment_mode text
  ops_type values: INVOICE, PAYMENT, RECEIPT, ADJUSTMENT
  stock_as values: normal(invoice), sample, lot, credit_note, purchase, transfer, damage, return

TABLE: ops_lines
  id uuid PK | ops_document_id uuid FK→ops_documents
  product_id uuid FK→products | sale_qty numeric | free_qty numeric
  gross_amount numeric | discount_amount numeric | tax_amount numeric | net_amount numeric

TABLE: financial_ledger
  id uuid PK | ops_document_id uuid FK→ops_documents
  party_id uuid FK→stockists | txn_date date
  debit numeric | credit numeric | gross_amount numeric
  discount_amount numeric | net_amount numeric
  closing_balance numeric | narration text

TABLE: stock_ledger
  id uuid PK | ops_document_id uuid FK→ops_documents
  product_id uuid FK→products | entity_type text | entity_id uuid
  txn_date date | qty_in numeric | qty_out numeric | closing_qty numeric
  direction text | narration text

TABLE: stockists
  id uuid PK | name text | territory_id uuid | assigned_user_id uuid | is_active boolean

TABLE: products
  id uuid PK | name text | is_active boolean

TABLE: users
  id uuid PK | username text | designation text | report_to uuid | is_active boolean
  designation values: MR, manager, senior_manager, admin

TABLE: dcr_reports
  id uuid PK | user_id uuid FK→users | report_date date | area_type text
  territory_ids uuid[] | submitted_at timestamp

TABLE: dcr_doctors_visited
  id uuid PK | dcr_report_id uuid FK→dcr_reports | doctor_id uuid
  visit_type text | remarks text

TABLE: tour_programmes
  id uuid PK | user_id uuid FK→users | month int | year int
  approved boolean | submitted_at timestamp

TABLE: payment_settlements
  id uuid PK | payment_ops_id uuid FK→ops_documents
  invoice_id uuid FK→ops_documents | amount numeric

TABLE: cnfs
  id uuid PK | name text | is_active boolean

TABLE: opening_balances (via ops_documents where ops_no LIKE 'OPEN-BAL-%')
  These are ops_documents with stock_as='opening_balance' or narration='Opening Balance'

IMPORTANT RULES:
- Always filter is_deleted=false for ops_documents unless specifically asked about deleted/archived records
- Payments: ops_type IN ('PAYMENT','RECEIPT')
- Invoices: stock_as='normal'
- Credit Notes: stock_as='credit_note'
- Money Received from stockist: direction='IN' on payment
- Outstanding balance = invoice_total - paid_amount
- For stockist balances: sum(debit) - sum(credit) from financial_ledger

DATA CONTEXT: The data provided below is freshly fetched from the database for this question. Use it to answer accurately.
"""


# ─────────────────────────────────────────────────────────────────
# USAGE TRACKING
# ─────────────────────────────────────────────────────────────────
def _get_usage(user_id: str) -> int:
    """Return how many questions the user has asked this calendar month."""
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


def _increment_usage(user_id: str):
    """Increment monthly question counter for the user."""
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


# ─────────────────────────────────────────────────────────────────
# SMART DATA FETCHER
# Analyses the question and fetches only the relevant rows
# ─────────────────────────────────────────────────────────────────
def _safe_query(query_fn):
    """Execute a Supabase query with retry on connection errors."""
    import time
    for attempt in range(3):
        try:
            return query_fn()
        except Exception as e:
            err = str(e).lower()
            if any(x in err for x in ["connectionterminated", "remoteerror",
                                        "connection", "timeout", "protocol"]):
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
                    continue
            return None
    return None


def _fetch_context(question: str, role: str, user_id: str) -> str:
    """
    Smart context builder — fetches relevant DB rows based on keywords
    in the question. Returns a formatted string injected into the prompt.
    """
    import time
    q = question.lower()
    context_parts = []

    # ── Date range detection ──────────────────────────────────────
    today = date.today()
    year  = today.year
    month = today.month

    # Look for month names
    month_map = {
        "january":1,"february":2,"march":3,"april":4,"may":5,"june":6,
        "july":7,"august":8,"september":9,"october":10,"november":11,"december":12,
        "jan":1,"feb":2,"mar":3,"apr":4,"jun":6,"jul":7,
        "aug":8,"sep":9,"oct":10,"nov":11,"dec":12
    }
    detected_month = None
    for m_name, m_num in month_map.items():
        if m_name in q:
            detected_month = m_num
            break

    if detected_month:
        from_date = date(year, detected_month, 1)
        _, last_day = monthrange(year, detected_month)
        to_date = date(year, detected_month, last_day)
    elif "today" in q:
        from_date = to_date = today
    elif "this month" in q or "current month" in q:
        from_date = date(year, month, 1)
        _, last_day = monthrange(year, month)
        to_date = date(year, month, last_day)
    elif "last month" in q:
        if month == 1:
            from_date = date(year-1, 12, 1)
            to_date = date(year-1, 12, 31)
        else:
            from_date = date(year, month-1, 1)
            _, last_day = monthrange(year, month-1)
            to_date = date(year, month-1, last_day)
    else:
        # Default: current year
        from_date = date(year, 1, 1)
        to_date = date(year, 12, 31)

    context_parts.append(f"Date range interpreted: {from_date} to {to_date}")
    context_parts.append(f"Today's date: {today}")

    # ── Stockist detection ────────────────────────────────────────
    stockists = safe_exec(
        admin_supabase.table("stockists")
        .select("id, name")
        .eq("is_active", True)
    ) or []
    stockist_map = {s["name"].lower(): s for s in stockists}

    matched_stockists = []
    for name_lower, s_data in stockist_map.items():
        # Check if any significant word from stockist name appears in question
        words = [w for w in name_lower.split() if len(w) > 3]
        if any(w in q for w in words) or name_lower in q:
            matched_stockists.append(s_data)

    # ── Scope filter for non-admin users ─────────────────────────
    user_stockist_ids = None
    if role != "admin":
        us = _safe_query(lambda: safe_exec(
            admin_supabase.table("user_stockists")
            .select("stockist_id")
            .eq("user_id", user_id)
        )) or []
        user_stockist_ids = [r["stockist_id"] for r in us]
        # Also include team if manager
        user_info = safe_exec(
            admin_supabase.table("users")
            .select("designation")
            .eq("id", user_id)
            .single()
        )
        if user_info and user_info.get("designation") in ("manager", "senior_manager"):
            reports = safe_exec(
                admin_supabase.table("users")
                .select("id")
                .eq("report_to", user_id)
                .eq("is_active", True)
            ) or []
            report_ids = [r["id"] for r in reports]
            if report_ids:
                extra = safe_exec(
                    admin_supabase.table("user_stockists")
                    .select("stockist_id")
                    .in_("user_id", report_ids)
                ) or []
                user_stockist_ids += [r["stockist_id"] for r in extra]

    # ── Products detection ────────────────────────────────────────
    products = safe_exec(
        admin_supabase.table("products")
        .select("id, name")
        .eq("is_active", True)
    ) or []
    matched_products = []
    for p in products:
        if p["name"].lower() in q or any(
            w in q for w in p["name"].lower().split() if len(w) > 4
        ):
            matched_products.append(p)

    # ── PAYMENT data ──────────────────────────────────────────────
    if any(w in q for w in ["payment", "paid", "receipt", "received", "collection"]):
        try:
            time.sleep(0.3)
            query = (
                admin_supabase.table("ops_documents")
                .select("ops_no, ops_date, ops_type, from_entity_type, from_entity_id, "
                        "to_entity_type, to_entity_id, invoice_total, paid_amount, "
                        "allocation_status, narration, payment_mode, reference_no")
                .in_("ops_type", ["PAYMENT", "RECEIPT"])
                .eq("is_deleted", False)
                .gte("ops_date", from_date.isoformat())
                .lte("ops_date", to_date.isoformat())
                .order("ops_date", desc=True)
                .limit(50)
            )
            payments = _safe_query(lambda: safe_exec(query)) or []

            # Filter by scope
            if user_stockist_ids is not None:
                payments = [
                    p for p in payments
                    if p.get("from_entity_id") in user_stockist_ids
                    or p.get("to_entity_id") in user_stockist_ids
                ]

            # Filter by matched stockist if specific one mentioned
            if matched_stockists:
                sids = {s["id"] for s in matched_stockists}
                payments = [
                    p for p in payments
                    if p.get("from_entity_id") in sids or p.get("to_entity_id") in sids
                ]

            # Enrich with stockist names
            all_entity_ids = list({
                p.get("from_entity_id") for p in payments
            } | {p.get("to_entity_id") for p in payments} - {None})

            if all_entity_ids:
                stk_names = safe_exec(
                    admin_supabase.table("stockists")
                    .select("id, name")
                    .in_("id", all_entity_ids)
                ) or []
                stk_name_map = {s["id"]: s["name"] for s in stk_names}
            else:
                stk_name_map = {}

            for p in payments:
                p["from_name"] = stk_name_map.get(p.get("from_entity_id"), p.get("from_entity_type", ""))
                p["to_name"]   = stk_name_map.get(p.get("to_entity_id"),   p.get("to_entity_type", ""))

            if payments:
                total = sum(float(p.get("invoice_total") or 0) for p in payments)
                context_parts.append(
                    f"\nPAYMENT DATA ({len(payments)} records, total ₹{total:,.2f}):\n" +
                    json.dumps(payments[:30], default=str, indent=2)
                )
        except Exception as e:
            context_parts.append(f"\nPayment data fetch error: {e}")

    # ── INVOICE data ──────────────────────────────────────────────
    if any(w in q for w in ["invoice", "sale", "billing", "outstanding", "due", "unpaid", "invoice total"]):
        try:
            time.sleep(0.3)
            query = (
                admin_supabase.table("ops_documents")
                .select("ops_no, ops_date, stock_as, from_entity_type, from_entity_id, "
                        "to_entity_type, to_entity_id, invoice_total, paid_amount, "
                        "outstanding_balance, payment_status, reference_no")
                .eq("stock_as", "normal")
                .eq("is_deleted", False)
                .gte("ops_date", from_date.isoformat())
                .lte("ops_date", to_date.isoformat())
                .order("ops_date", desc=True)
                .limit(50)
            )
            invoices = _safe_query(lambda: safe_exec(query)) or []

            if user_stockist_ids is not None:
                invoices = [
                    i for i in invoices
                    if i.get("from_entity_id") in user_stockist_ids
                    or i.get("to_entity_id") in user_stockist_ids
                ]
            if matched_stockists:
                sids = {s["id"] for s in matched_stockists}
                invoices = [
                    i for i in invoices
                    if i.get("from_entity_id") in sids or i.get("to_entity_id") in sids
                ]

            # Enrich with stockist names
            all_ids = list({i.get("from_entity_id") for i in invoices} |
                          {i.get("to_entity_id") for i in invoices} - {None})
            if all_ids:
                stk = safe_exec(
                    admin_supabase.table("stockists").select("id, name").in_("id", all_ids)
                ) or []
                smap = {s["id"]: s["name"] for s in stk}
            else:
                smap = {}
            for i in invoices:
                i["from_name"] = smap.get(i.get("from_entity_id"), i.get("from_entity_type", ""))
                i["to_name"]   = smap.get(i.get("to_entity_id"),   i.get("to_entity_type", ""))

            if invoices:
                total = sum(float(i.get("invoice_total") or 0) for i in invoices)
                outstanding = sum(float(i.get("outstanding_balance") or 0) for i in invoices)
                context_parts.append(
                    f"\nINVOICE DATA ({len(invoices)} records, total ₹{total:,.2f}, "
                    f"outstanding ₹{outstanding:,.2f}):\n" +
                    json.dumps(invoices[:30], default=str, indent=2)
                )
        except Exception as e:
            context_parts.append(f"\nInvoice data fetch error: {e}")

    # ── CREDIT NOTE data ──────────────────────────────────────────
    if any(w in q for w in ["credit note", "cn", "credit", "return"]):
        try:
            cns = safe_exec(
                admin_supabase.table("ops_documents")
                .select("ops_no, ops_date, stock_as, from_entity_type, from_entity_id, "
                        "to_entity_type, to_entity_id, invoice_total, reference_no, narration")
                .eq("stock_as", "credit_note")
                .eq("is_deleted", False)
                .gte("ops_date", from_date.isoformat())
                .lte("ops_date", to_date.isoformat())
                .order("ops_date", desc=True)
                .limit(30)
            ) or []
            if cns:
                total = sum(float(c.get("invoice_total") or 0) for c in cns)
                context_parts.append(
                    f"\nCREDIT NOTE DATA ({len(cns)} records, total ₹{total:,.2f}):\n" +
                    json.dumps(cns[:20], default=str, indent=2)
                )
        except Exception as e:
            context_parts.append(f"\nCredit note data fetch error: {e}")

    # ── STOCK data ────────────────────────────────────────────────
    if any(w in q for w in ["stock", "inventory", "closing", "opening stock", "qty", "quantity"]):
        try:
            sl_query = (
                admin_supabase.table("stock_ledger")
                .select("product_id, entity_type, entity_id, txn_date, "
                        "qty_in, qty_out, closing_qty, narration")
                .gte("txn_date", from_date.isoformat())
                .lte("txn_date", to_date.isoformat())
                .order("txn_date", desc=True)
                .limit(60)
            )
            if matched_products:
                pids = [p["id"] for p in matched_products]
                sl_query = sl_query.in_("product_id", pids)

            stock_rows = safe_exec(sl_query) or []

            # Enrich with product names
            pids_in_data = list({r["product_id"] for r in stock_rows if r.get("product_id")})
            if pids_in_data:
                pnames = safe_exec(
                    admin_supabase.table("products").select("id, name").in_("id", pids_in_data)
                ) or []
                pmap = {p["id"]: p["name"] for p in pnames}
                for r in stock_rows:
                    r["product_name"] = pmap.get(r["product_id"], "Unknown")

            if stock_rows:
                context_parts.append(
                    f"\nSTOCK LEDGER DATA ({len(stock_rows)} records):\n" +
                    json.dumps(stock_rows[:40], default=str, indent=2)
                )
        except Exception as e:
            context_parts.append(f"\nStock data fetch error: {e}")

    # ── LEDGER / BALANCE data ─────────────────────────────────────
    if any(w in q for w in ["ledger", "balance", "party balance", "account", "debit", "credit balance"]):
        try:
            if matched_stockists:
                sids = [s["id"] for s in matched_stockists]
                led = safe_exec(
                    admin_supabase.table("financial_ledger")
                    .select("txn_date, debit, credit, narration, ops_document_id, party_id")
                    .in_("party_id", sids)
                    .gte("txn_date", from_date.isoformat())
                    .lte("txn_date", to_date.isoformat())
                    .order("txn_date", desc=True)
                    .limit(40)
                ) or []
            else:
                led = []

            if led:
                total_debit  = sum(float(r.get("debit") or 0) for r in led)
                total_credit = sum(float(r.get("credit") or 0) for r in led)
                context_parts.append(
                    f"\nFINANCIAL LEDGER DATA ({len(led)} records, "
                    f"total debit ₹{total_debit:,.2f}, total credit ₹{total_credit:,.2f}):\n" +
                    json.dumps(led[:30], default=str, indent=2)
                )
        except Exception as e:
            context_parts.append(f"\nLedger data fetch error: {e}")

    # ── DCR data ──────────────────────────────────────────────────
    if any(w in q for w in ["dcr", "doctor visit", "call report", "doctor", "visit"]):
        try:
            dcr_query = (
                admin_supabase.table("dcr_reports")
                .select("id, user_id, report_date, area_type, submitted_at")
                .gte("report_date", from_date.isoformat())
                .lte("report_date", to_date.isoformat())
                .order("report_date", desc=True)
                .limit(30)
            )
            if role != "admin":
                dcr_query = dcr_query.eq("user_id", user_id)

            dcrs = safe_exec(dcr_query) or []
            if dcrs:
                context_parts.append(
                    f"\nDCR DATA ({len(dcrs)} reports):\n" +
                    json.dumps(dcrs[:20], default=str, indent=2)
                )
        except Exception as e:
            context_parts.append(f"\nDCR data fetch error: {e}")

    # ── General summary if no specific data type detected ─────────
    if len(context_parts) <= 2:
        try:
            # Give a broad summary of recent activity
            recent = safe_exec(
                admin_supabase.table("ops_documents")
                .select("ops_no, ops_date, ops_type, stock_as, invoice_total, payment_status")
                .eq("is_deleted", False)
                .gte("ops_date", from_date.isoformat())
                .lte("ops_date", to_date.isoformat())
                .order("ops_date", desc=True)
                .limit(20)
            ) or []
            if recent:
                context_parts.append(
                    f"\nRECENT ACTIVITY ({len(recent)} records):\n" +
                    json.dumps(recent, default=str, indent=2)
                )
        except Exception:
            pass

    return "\n\n".join(context_parts)


# ─────────────────────────────────────────────────────────────────
# CLAUDE API CALL
# ─────────────────────────────────────────────────────────────────
def _ask_claude(question: str, history: list, context: str) -> str:
    """Call Claude API and return the answer string."""
    import requests

    # Build conversation messages
    messages = []
    # Include last 6 turns of history for context
    for turn in history[-6:]:
        messages.append({"role": "user",      "content": turn["question"]})
        messages.append({"role": "assistant", "content": turn["answer"]})

    # Add current question with fetched data
    user_content = f"""DATABASE CONTEXT (freshly fetched for this question):
{context}

USER QUESTION: {question}"""

    messages.append({"role": "user", "content": user_content})

    try:
        api_key = ""
        try:
            api_key = st.secrets["ANTHROPIC_API_KEY"]
        except Exception:
            pass
        if not api_key:
            import os
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            return "⚠️ Claude API key not configured. Please add ANTHROPIC_API_KEY to your Streamlit secrets."

        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key":         api_key,
                "anthropic-version": "2023-06-01",
                "content-type":      "application/json",
            },
            json={
                "model":      MODEL,
                "max_tokens": MAX_TOKENS,
                "system":     SYSTEM_PROMPT,
                "messages":   messages,
            },
            timeout=30,
        )

        if response.status_code == 200:
            data = response.json()
            return data["content"][0]["text"]
        elif response.status_code == 429:
            return "⚠️ Rate limit reached. Please wait a moment and try again."
        elif response.status_code == 401:
            return "⚠️ Invalid API key. Please check your ANTHROPIC_API_KEY in Streamlit secrets."
        else:
            return f"⚠️ API error {response.status_code}: {response.text[:200]}"

    except requests.exceptions.Timeout:
        return "⚠️ Request timed out. Please try again."
    except Exception as e:
        return f"⚠️ Error calling Claude API: {str(e)}"


# ─────────────────────────────────────────────────────────────────
# MAIN UI
# ─────────────────────────────────────────────────────────────────
def run_ai_assistant():
    """Main entry point — renders the AI assistant UI on the home page."""

    user     = st.session_state.get("auth_user")
    role     = st.session_state.get("role", "user")
    user_id  = user.id if user else None

    # Session state keys for this module
    if "ai_history" not in st.session_state:
        st.session_state.ai_history = []
    if "ai_input_key" not in st.session_state:
        st.session_state.ai_input_key = 0

    # ── Usage check ───────────────────────────────────────────────
    limit   = MONTHLY_LIMIT_ADMIN if role == "admin" else MONTHLY_LIMIT_USER
    used    = _get_usage(user_id) if user_id else 0
    remaining = max(0, limit - used)

    # ── Header ────────────────────────────────────────────────────
    st.markdown("### 🤖 Ivy Assistant")
    st.caption(
        f"Ask anything about sales, payments, stock, reports, or doctors. "
        f"**{remaining}** questions remaining this month."
    )

    if remaining == 0:
        st.warning(
            f"You have used all {limit} questions for this month. "
            "Your limit resets on the 1st of next month."
        )
        return

    # ── Conversation history ──────────────────────────────────────
    history = st.session_state.ai_history

    if history:
        for i, turn in enumerate(history):
            # User bubble
            st.markdown(
                f"""<div style="
                    background:#e8f5f1; border-radius:10px 10px 2px 10px;
                    padding:0.6rem 0.9rem; margin:0.4rem 0 0.2rem auto;
                    max-width:85%; width:fit-content; margin-left:auto;
                    font-size:0.9rem; color:#1c2b27;
                ">🧑 {turn['question']}</div>""",
                unsafe_allow_html=True
            )
            # Assistant bubble
            st.markdown(
                f"""<div style="
                    background:#ffffff; border:1px solid #e2ece9;
                    border-radius:10px 10px 10px 2px;
                    padding:0.6rem 0.9rem; margin:0.2rem auto 0.4rem 0;
                    max-width:90%; font-size:0.9rem; color:#1c2b27;
                ">🌿 {turn['answer']}</div>""",
                unsafe_allow_html=True
            )

        if st.button("🗑 Clear conversation", key="ai_clear"):
            st.session_state.ai_history = []
            st.rerun()

    # ── Suggested questions ───────────────────────────────────────
    if not history:
        st.markdown("**Try asking:**")
        suggestions = [
            "What are the total payments received this month?",
            "Which stockists have outstanding invoices?",
            "What is the closing stock of IVYNORMRZ at CNF?",
            "Show me the top 5 stockists by sales in March",
            "How many DCR reports were submitted this month?",
        ]
        cols = st.columns(2)
        for i, s in enumerate(suggestions):
            with cols[i % 2]:
                if st.button(s, key=f"suggest_{i}", use_container_width=True):
                    st.session_state[f"ai_prefill"] = s
                    st.rerun()

    # ── Input box ─────────────────────────────────────────────────
    prefill = st.session_state.pop("ai_prefill", "") if "ai_prefill" in st.session_state else ""

    with st.form(key=f"ai_form_{st.session_state.ai_input_key}", clear_on_submit=True):
        question = st.text_input(
            "Your question",
            value=prefill,
            placeholder="e.g. What are the total sales for NEW SANTOSH AGENCY in March?",
            label_visibility="collapsed"
        )
        col1, col2 = st.columns([5, 1])
        with col2:
            submitted = st.form_submit_button("Ask →", type="primary", use_container_width=True)

    if submitted and question.strip():
        with st.spinner("Fetching data and thinking..."):
            # Fetch relevant DB context
            context = _fetch_context(question.strip(), role, user_id)

            # Call Claude
            answer = _ask_claude(question.strip(), history, context)

            # Save to history
            st.session_state.ai_history.append({
                "question": question.strip(),
                "answer":   answer,
                "timestamp": datetime.utcnow().isoformat()
            })

            # Increment usage counter
            if user_id:
                _increment_usage(user_id)

            # Reset form
            st.session_state.ai_input_key += 1
            st.rerun()
