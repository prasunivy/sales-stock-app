"""
OPS Reports Module — modules/statement/ops_reports.py
5 matrix reports built from ops_documents + ops_lines.
Called from run_reports() in statement_main.py via tab2.

Report 1 : Product x Month  ->  Invoice qty | Sample qty | Lot qty
           Filter by: Company / CNF / User (multi-select)

Report 2 : Month x (Payment | Credit Note amount)
           Filter by: User -> Stockist

Report 3 : Same layout as R2 (separate stockist selection)

Report 4 : Month x (Gross Invoice | Credit Note amount)
           Filter by: User -> Stockist

Report 5 : Month x (Gross Invoice | Net Invoice | Payment | Freight | Credit Note)
           Filter by: User -> Stockist

Access control:
  admin  -> can select any user / any stockist
  user   -> sees only own stockists, no user selector shown
"""

import streamlit as st
import pandas as pd
from datetime import date
from io import BytesIO
from anchors.supabase_client import admin_supabase, safe_exec


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

MONTH_SHORT = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr",
    5: "May", 6: "Jun", 7: "Jul", 8: "Aug",
    9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}

YEAR_OPTIONS = list(range(2023, date.today().year + 2))


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _mlabel(year, month):
    """Return 'Jan-25' style label."""
    return f"{MONTH_SHORT[month]}-{str(year)[-2:]}"


def _period_range(yf, mf, yt, mt):
    """Return list of (year, month) tuples in chronological order."""
    result, y, m = [], yf, mf
    while (y, m) <= (yt, mt):
        result.append((y, m))
        m += 1
        if m == 13:
            m, y = 1, y + 1
    return result


def _safe_float(v):
    try:
        return float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


# ─────────────────────────────────────────────────────────────────────────────
# DATA LOADERS
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def _load_all_users():
    rows = safe_exec(
        admin_supabase.table("users")
        .select("id, username")
        .eq("is_active", True)
        .order("username")
    ) or []
    return rows


@st.cache_data(ttl=300)
def _load_all_cnfs():
    rows = safe_exec(
        admin_supabase.table("cnfs")
        .select("id, name")
        .eq("is_active", True)
        .order("name")
    ) or []
    return rows


def _load_stockists_for_users(user_ids):
    """Return unique stockists assigned to given user_ids."""
    if not user_ids:
        return []
    rows = safe_exec(
        admin_supabase.table("user_stockists")
        .select("stockist_id, stockists(id, name)")
        .in_("user_id", user_ids)
    ) or []
    seen = {}
    for r in rows:
        s = r.get("stockists")
        if s:
            seen[s["id"]] = s["name"]
    return [{"id": k, "name": v} for k, v in sorted(seen.items(), key=lambda x: x[1])]


# ─────────────────────────────────────────────────────────────────────────────
# PDF GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

def _build_pdf(report_title, subtitle, df):
    """
    Generate a formatted A4 / landscape PDF from a DataFrame.
    Returns bytes ready for st.download_button.
    """
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle,
        Paragraph, Spacer,
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    buf = BytesIO()
    n_cols = len(df.reset_index().columns)
    page_size = landscape(A4) if n_cols > 6 else A4

    doc = SimpleDocTemplate(
        buf, pagesize=page_size,
        leftMargin=1 * cm, rightMargin=1 * cm,
        topMargin=1.5 * cm, bottomMargin=1 * cm,
    )

    styles = getSampleStyleSheet()
    ivy_green = colors.HexColor("#1a6b5a")
    row_shade = colors.HexColor("#e8f5f1")

    h1 = ParagraphStyle("h1", parent=styles["Heading1"],
                         textColor=ivy_green, fontSize=13, spaceAfter=3)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"],
                         textColor=colors.HexColor("#1c2b27"), fontSize=10, spaceAfter=2)
    sub = ParagraphStyle("sub", parent=styles["Normal"],
                          textColor=colors.HexColor("#5a7268"), fontSize=8, spaceAfter=10)
    foot = ParagraphStyle("foot", parent=styles["Normal"],
                           textColor=colors.HexColor("#aaaaaa"), fontSize=7)

    story = [
        Paragraph("Ivy Pharmaceuticals", h1),
        Paragraph(report_title, h2),
        Paragraph(subtitle, sub),
        Spacer(1, 0.2 * cm),
    ]

    # Build table data
    df_out = df.reset_index()
    headers = list(df_out.columns)
    rows_data = [headers]
    for _, row in df_out.iterrows():
        rows_data.append([
            "" if pd.isna(v) else (str(int(v)) if isinstance(v, float) and v == int(v) else str(v))
            for v in row
        ])

    # Column widths: first column wider
    usable_w = page_size[0] - 2 * cm
    first_w  = min(4.0 * cm, usable_w * 0.28)
    rest_w   = (usable_w - first_w) / max(len(headers) - 1, 1)
    col_widths = [first_w] + [rest_w] * (len(headers) - 1)

    tbl = Table(rows_data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        # Header row
        ("BACKGROUND",    (0, 0), (-1, 0), ivy_green),
        ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0), 7.5),
        ("ALIGN",         (0, 0), (-1, 0), "CENTER"),
        ("TOPPADDING",    (0, 0), (-1, 0), 5),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
        # Data rows
        ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",      (0, 1), (-1, -1), 7),
        ("ALIGN",         (1, 1), (-1, -1), "CENTER"),
        ("ALIGN",         (0, 1), (0, -1), "LEFT"),
        ("TOPPADDING",    (0, 1), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 3),
        # Total row bold
        ("FONTNAME",      (0, -1), (-1, -1), "Helvetica-Bold"),
        # Alternating row shading
        *[("BACKGROUND", (0, i), (-1, i), row_shade)
          for i in range(2, len(rows_data), 2)],
        # Grid
        ("GRID",          (0, 0), (-1, -1), 0.35, colors.HexColor("#c5ddd8")),
        ("LINEBELOW",     (0, 0), (-1, 0), 1.2, ivy_green),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(
        f"Generated on {date.today().strftime('%d %b %Y')} -- Ivy Pharmaceuticals",
        foot,
    ))

    doc.build(story)
    buf.seek(0)
    return buf.read()


# ─────────────────────────────────────────────────────────────────────────────
# PERIOD FILTER WIDGET (shared)
# ─────────────────────────────────────────────────────────────────────────────

def _period_selectors(key):
    """Render year/month from-to selectors. Returns (yf, mf, yt, mt)."""
    today = date.today()
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        yf = st.selectbox("Year From",  YEAR_OPTIONS,
                          index=YEAR_OPTIONS.index(today.year), key=f"{key}_yf")
    with c2:
        mf = st.selectbox("Month From", list(range(1, 13)),
                          format_func=lambda x: MONTH_SHORT[x],
                          index=0, key=f"{key}_mf")
    with c3:
        yt = st.selectbox("Year To",    YEAR_OPTIONS,
                          index=YEAR_OPTIONS.index(today.year), key=f"{key}_yt")
    with c4:
        mt = st.selectbox("Month To",   list(range(1, 13)),
                          format_func=lambda x: MONTH_SHORT[x],
                          index=today.month - 1, key=f"{key}_mt")
    return yf, mf, yt, mt


# ─────────────────────────────────────────────────────────────────────────────
# USER + STOCKIST SELECTOR (shared for R2-R5)
# ─────────────────────────────────────────────────────────────────────────────

def _user_and_stockist_selectors(key, role, current_user_id):
    """
    Returns (selected_user_ids, selected_stockist_ids, stockist_label).
    Admin: shows user multiselect then stockist multiselect.
    User:  auto-scoped to self; shows only stockist multiselect.
    """
    if role == "admin":
        all_users = _load_all_users()
        sel_users = st.multiselect(
            "Select User(s)", all_users,
            default=all_users,
            format_func=lambda x: x["username"],
            key=f"{key}_users",
        )
        sel_user_ids = [u["id"] for u in sel_users]
    else:
        sel_user_ids = [current_user_id]
        st.caption("Showing stockists assigned to you.")

    if not sel_user_ids:
        st.info("Select at least one user to see stockists.")
        return [], [], ""

    avail_stockists = _load_stockists_for_users(sel_user_ids)
    if not avail_stockists:
        st.warning("No stockists found for selected user(s).")
        return sel_user_ids, [], ""

    sel_stockists = st.multiselect(
        "Select Stockist(s)", avail_stockists,
        default=avail_stockists,
        format_func=lambda x: x["name"],
        key=f"{key}_stockists",
    )
    stockist_ids = [s["id"] for s in sel_stockists]

    label_parts = [s["name"] for s in sel_stockists[:3]]
    label = ", ".join(label_parts)
    if len(sel_stockists) > 3:
        label += f" +{len(sel_stockists) - 3} more"

    return sel_user_ids, stockist_ids, label


# ─────────────────────────────────────────────────────────────────────────────
# REPORT 1 - Product x Month  (Invoice / Sample / Lot quantities)
# ─────────────────────────────────────────────────────────────────────────────

def _report1(role, user_id):
    st.markdown("#### Report 1 - Product x Month: Invoice / Sample / Lot Quantities")
    st.caption(
        "Rows = Products.  Columns = Month -> Invoice qty | Sample qty | Lot qty.  "
        "Filter by Company, CNF, or User."
    )

    yf, mf, yt, mt = _period_selectors("r1")

    entity_type = st.selectbox("Filter By", ["Company", "CNF", "User"], key="r1_etype")

    entity_ids   = []
    entity_label = ""

    if entity_type == "Company":
        entity_ids   = ["company"]
        entity_label = "Company"

    elif entity_type == "CNF":
        cnfs = _load_all_cnfs()
        if not cnfs:
            st.warning("No CNFs found in the system.")
            return
        sel = st.multiselect("Select CNF(s)", cnfs, default=cnfs,
                             format_func=lambda x: x["name"], key="r1_cnf")
        entity_ids   = [c["id"] for c in sel]
        entity_label = ", ".join(c["name"] for c in sel) or "-"

    else:  # User
        if role == "admin":
            all_users = _load_all_users()
            sel = st.multiselect("Select User(s)", all_users, default=all_users,
                                 format_func=lambda x: x["username"], key="r1_users")
            entity_ids   = [u["id"] for u in sel]
            entity_label = ", ".join(u["username"] for u in sel) or "-"
        else:
            entity_ids   = [user_id]
            entity_label = st.session_state.get("username", "Me")
            st.caption("Showing your own transactions.")

    if not entity_ids:
        st.info("Select at least one entity to generate the report.")
        return

    if not st.button("Generate Report 1", key="r1_btn", type="primary"):
        return

    with st.spinner("Fetching data..."):
        from_date = date(yf, mf, 1)
        to_date   = date(yt, 12, 31) if mt == 12 else date(yt, mt + 1, 1)

        docs_raw = safe_exec(
            admin_supabase.table("ops_documents")
            .select("id, ops_date, stock_as, direction,"
                    "from_entity_type, from_entity_id,"
                    "to_entity_type,   to_entity_id")
            .in_("stock_as", ["normal", "sample", "lot"])
            .gte("ops_date", from_date.isoformat())
            .lt("ops_date",  to_date.isoformat())
            .eq("is_deleted", False)
        ) or []

    if not docs_raw:
        st.info("No Invoice / Sample / Lot documents found for this period.")
        return

    def _matches(doc):
        if entity_type == "Company":
            return (
                (doc.get("from_entity_type") or "").lower() == "company" or
                (doc.get("to_entity_type")   or "").lower() == "company"
            )
        else:
            return (
                doc.get("from_entity_id") in entity_ids or
                doc.get("to_entity_id")   in entity_ids
            )

    filtered_docs = [d for d in docs_raw if _matches(d)]
    if not filtered_docs:
        st.info("No documents match the selected entity filter.")
        return

    doc_id_to_info = {
        d["id"]: (d["ops_date"], d["stock_as"])
        for d in filtered_docs
    }
    doc_ids = list(doc_id_to_info.keys())

    with st.spinner("Fetching product lines..."):
        lines_raw = safe_exec(
            admin_supabase.table("ops_lines")
            .select("ops_document_id, sale_qty, product_id")
            .in_("ops_document_id", doc_ids)
        ) or []

    if not lines_raw:
        st.info("No product lines found for the matching documents.")
        return

    # Build product_id -> name lookup
    all_product_ids = list({ln["product_id"] for ln in lines_raw if ln.get("product_id")})
    products_raw = safe_exec(
        admin_supabase.table("products")
        .select("id, name")
        .in_("id", all_product_ids)
    ) or []
    product_name_map = {p["id"]: p["name"] for p in products_raw}

    periods    = _period_range(yf, mf, yt, mt)
    period_set = {(y, m) for y, m in periods}

    agg = {}
    for ln in lines_raw:
        doc_id = ln["ops_document_id"]
        if doc_id not in doc_id_to_info:
            continue
        ops_date, stock_as = doc_id_to_info[doc_id]
        y, mo = int(ops_date[:4]), int(ops_date[5:7])
        if (y, mo) not in period_set:
            continue
        product  = product_name_map.get(ln.get("product_id"), "Unknown")
        qty      = _safe_float(ln.get("sale_qty"))
        type_key = "Invoice" if stock_as == "normal" else stock_as.capitalize()
        k        = (product, y, mo, type_key)
        agg[k]   = agg.get(k, 0.0) + qty

    if not agg:
        st.info("No data to display after aggregation.")
        return

    rows_list = [
        {"Product": p, "Period": _mlabel(y, mo), "Type": t, "Qty": v}
        for (p, y, mo, t), v in agg.items()
    ]
    df_raw = pd.DataFrame(rows_list)

    period_labels = [_mlabel(y, m) for y, m in periods]
    type_order    = ["Invoice", "Sample", "Lot"]

    pivot = df_raw.pivot_table(
        index="Product", columns=["Period", "Type"],
        values="Qty", aggfunc="sum", fill_value=0,
    )

    ordered_cols = [
        (p, t) for p in period_labels for t in type_order
        if (p, t) in pivot.columns
    ]
    pivot = pivot.reindex(columns=ordered_cols, fill_value=0).astype(int)

    st.dataframe(pivot, use_container_width=True)

    subtitle  = (f"Entity: {entity_label}  |  "
                 f"Period: {_mlabel(yf, mf)} - {_mlabel(yt, mt)}")
    pdf_bytes = _build_pdf("Report 1 - Product x Month (Invoice / Sample / Lot)", subtitle, pivot)
    st.download_button(
        "Download PDF", data=pdf_bytes,
        file_name="r1_product_month_matrix.pdf",
        mime="application/pdf", key="r1_pdf",
    )


# ─────────────────────────────────────────────────────────────────────────────
# SHARED ENGINE - Stockist financial matrix (Reports 2-5)
# ─────────────────────────────────────────────────────────────────────────────

def _stockist_financial_matrix(key, role, user_id, col_specs, report_title):
    """
    col_specs: ordered list of (col_key, col_label) pairs.
    col_key values: PAYMENT | CREDIT_NOTE | INVOICE_GROSS | INVOICE_NET | FREIGHT

    Fetches ops_documents + ops_lines for the selected stockists in the date range,
    aggregates into a Month x col_label matrix, adds TOTAL row, shows PDF download.
    """
    yf, mf, yt, mt = _period_selectors(key)

    _user_ids, stockist_ids, stockist_label = _user_and_stockist_selectors(
        key, role, user_id
    )

    if not stockist_ids:
        return

    if not st.button(f"Generate {report_title.split('-')[0].strip()}", key=f"{key}_btn", type="primary"):
        return

    with st.spinner("Fetching data..."):
        from_date = date(yf, mf, 1)
        to_date   = date(yt, 12, 31) if mt == 12 else date(yt, mt + 1, 1)
        periods   = _period_range(yf, mf, yt, mt)

        docs_raw = safe_exec(
            admin_supabase.table("ops_documents")
            .select("id, ops_date, ops_type, stock_as, narration,"
                    "invoice_total, paid_amount,"
                    "from_entity_type, from_entity_id,"
                    "to_entity_type,   to_entity_id")
            .gte("ops_date", from_date.isoformat())
            .lt("ops_date",  to_date.isoformat())
            .eq("is_deleted", False)
        ) or []

        def _involves_stockist(d):
            return (
                (d.get("from_entity_type") or "").lower() == "stockist"
                and d.get("from_entity_id") in stockist_ids
            ) or (
                (d.get("to_entity_type") or "").lower() == "stockist"
                and d.get("to_entity_id") in stockist_ids
            )

        docs = [d for d in docs_raw if _involves_stockist(d)]

        if not docs:
            st.info("No transactions found for the selected stockists in this period.")
            return

        doc_ids  = [d["id"] for d in docs]
        col_keys = [ck for ck, _ in col_specs]

        # Fetch lines only when gross/net/credit columns are required
        lines_map = {}
        need_lines = any(c in col_keys for c in ("INVOICE_GROSS", "INVOICE_NET", "CREDIT_NOTE"))
        if need_lines:
            lines_raw = safe_exec(
                admin_supabase.table("ops_lines")
                .select("ops_document_id, gross_amount, net_amount")
                .in_("ops_document_id", doc_ids)
            ) or []
            for ln in lines_raw:
                oid = ln["ops_document_id"]
                if oid not in lines_map:
                    lines_map[oid] = {"gross": 0.0, "net": 0.0}
                lines_map[oid]["gross"] += _safe_float(ln.get("gross_amount"))
                lines_map[oid]["net"]   += _safe_float(ln.get("net_amount"))

        # Aggregate by period
        period_set = {(y, m) for y, m in periods}
        agg = {(y, m): {ck: 0.0 for ck, _ in col_specs} for y, m in periods}

        for d in docs:
            ops_date  = d["ops_date"]
            y, mo     = int(ops_date[:4]), int(ops_date[5:7])
            if (y, mo) not in period_set:
                continue
            stock_as  = (d.get("stock_as")  or "").lower()
            ops_type  = (d.get("ops_type")  or "").upper()
            narration = (d.get("narration") or "").lower()
            ld        = lines_map.get(d["id"], {"gross": 0.0, "net": 0.0})

            if "PAYMENT" in col_keys and ops_type in ("PAYMENT", "RECEIPT"):
                agg[(y, mo)]["PAYMENT"] += _safe_float(
                    d.get("invoice_total") or d.get("paid_amount")
                )

            if "CREDIT_NOTE" in col_keys and stock_as == "credit_note":
                amt = ld["net"] if ld["net"] > 0 else _safe_float(d.get("invoice_total"))
                agg[(y, mo)]["CREDIT_NOTE"] += amt

            if "INVOICE_GROSS" in col_keys and stock_as == "normal":
                amt = ld["gross"] if ld["gross"] > 0 else _safe_float(d.get("invoice_total"))
                agg[(y, mo)]["INVOICE_GROSS"] += amt

            if "INVOICE_NET" in col_keys and stock_as == "normal":
                amt = ld["net"] if ld["net"] > 0 else _safe_float(d.get("invoice_total"))
                agg[(y, mo)]["INVOICE_NET"] += amt

            if "FREIGHT" in col_keys and "freight" in narration:
                agg[(y, mo)]["FREIGHT"] += _safe_float(d.get("invoice_total"))

    # Build DataFrame
    table_rows = []
    for y, mo in periods:
        row = {"Month": _mlabel(y, mo)}
        for ck, cl in col_specs:
            row[cl] = round(agg[(y, mo)][ck], 2)
        table_rows.append(row)

    df = pd.DataFrame(table_rows).set_index("Month")
    df.loc["TOTAL"] = df.sum()

    st.dataframe(df, use_container_width=True)

    subtitle  = (f"Stockists: {stockist_label}  |  "
                 f"Period: {_mlabel(yf, mf)} - {_mlabel(yt, mt)}")
    pdf_bytes = _build_pdf(report_title, subtitle, df)
    st.download_button(
        "Download PDF", data=pdf_bytes,
        file_name=f"{key}_matrix.pdf",
        mime="application/pdf", key=f"{key}_pdf",
    )


# ─────────────────────────────────────────────────────────────────────────────
# REPORT 2
# ─────────────────────────────────────────────────────────────────────────────

def _report2(role, user_id):
    st.markdown("#### Report 2 - Payment & Credit Note by Month")
    st.caption("Rows = Month.  Columns = Payment amount | Credit Note amount.")
    _stockist_financial_matrix(
        key="r2", role=role, user_id=user_id,
        col_specs=[("PAYMENT", "Payment"), ("CREDIT_NOTE", "Credit Note")],
        report_title="Report 2 - Payment & Credit Note by Month",
    )


# ─────────────────────────────────────────────────────────────────────────────
# REPORT 3
# ─────────────────────────────────────────────────────────────────────────────

def _report3(role, user_id):
    st.markdown("#### Report 3 - Payment & Credit Note (Alternate Selection)")
    st.caption("Same columns as Report 2. Use for a different stockist grouping.")
    _stockist_financial_matrix(
        key="r3", role=role, user_id=user_id,
        col_specs=[("PAYMENT", "Payment"), ("CREDIT_NOTE", "Credit Note")],
        report_title="Report 3 - Payment & Credit Note (Alt Selection)",
    )


# ─────────────────────────────────────────────────────────────────────────────
# REPORT 4
# ─────────────────────────────────────────────────────────────────────────────

def _report4(role, user_id):
    st.markdown("#### Report 4 - Gross Invoice & Credit Note by Month")
    st.caption("Rows = Month.  Columns = Gross Invoice amount | Credit Note amount.")
    _stockist_financial_matrix(
        key="r4", role=role, user_id=user_id,
        col_specs=[("INVOICE_GROSS", "Gross Invoice"), ("CREDIT_NOTE", "Credit Note")],
        report_title="Report 4 - Gross Invoice & Credit Note by Month",
    )


# ─────────────────────────────────────────────────────────────────────────────
# REPORT 5
# ─────────────────────────────────────────────────────────────────────────────

def _report5(role, user_id):
    st.markdown("#### Report 5 - Full Financial Summary by Month")
    st.caption(
        "Rows = Month.  "
        "Columns = Gross Invoice | Net Invoice | Payment | Freight | Credit Note."
    )
    _stockist_financial_matrix(
        key="r5", role=role, user_id=user_id,
        col_specs=[
            ("INVOICE_GROSS", "Gross Invoice"),
            ("INVOICE_NET",   "Net Invoice"),
            ("PAYMENT",       "Payment"),
            ("FREIGHT",       "Freight"),
            ("CREDIT_NOTE",   "Credit Note"),
        ],
        report_title="Report 5 - Full Financial Summary by Month",
    )


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT - called from statement_main.py -> run_reports() -> tab2
# ─────────────────────────────────────────────────────────────────────────────

def run_ops_reports():
    """
    Entry point. Renders 5 sub-tabs inside the OPS Reports tab.
    Called from run_reports() in statement_main.py.
    """
    user_id = st.session_state.auth_user.id
    role    = st.session_state.get("role", "user")

    st.markdown("##### OPS matrix reports drawn from invoices, payments, credit notes, samples and lots.")
    if role != "admin":
        st.caption("You can see data for your own stockists only.")

    tabs = st.tabs([
        "R1 - Product x Month",
        "R2 - Payment & Credit Note",
        "R3 - Payment & Credit Note (Alt)",
        "R4 - Gross Invoice & Credit Note",
        "R5 - Full Financial Summary",
    ])

    with tabs[0]:
        _report1(role, user_id)

    with tabs[1]:
        _report2(role, user_id)

    with tabs[2]:
        _report3(role, user_id)

    with tabs[3]:
        _report4(role, user_id)

    with tabs[4]:
        _report5(role, user_id)
