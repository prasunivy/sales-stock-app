"""
OPS Reports Module — modules/statement/ops_reports.py
4 matrix reports built from ops_documents + ops_lines + financial_ledger.
Called from run_reports() in statement_main.py via tab2.

All reports filter by: User(s) -> Stockist(s) -> Month From/To.
Documents are matched to stockists by entity_id (invoices: to_entity_id,
credit notes & payments: from_entity_id). Cancelled payments are excluded.

Report 1 : Product (rows) x Month -> Invoice qty | Credit Note qty
Report 2 : Payment | Credit Note (rows) x Month (cols)
Report 4 : Gross Invoice | Credit Note (rows) x Month (cols)
Report 5 : Gross Invoice | Net Invoice | Credit Note | Payment Gross |
           Discount | Payment Net (rows) x Month (cols)

Access control:
  admin   -> can select any user / any stockist
  manager -> own + direct reports
  user    -> own stockists only
"""

import streamlit as st
import pandas as pd


def _mobile_table(df, compact_cols, detail_title_col, uid_prefix='tbl'):
    import json, uuid
    import streamlit.components.v1 as components
    table_id = uid_prefix + '_' + uuid.uuid4().hex[:6]
    rows = df.fillna('').astype(str).to_dict(orient='records')
    all_cols = list(df.columns)
    rj = json.dumps(rows); cj = json.dumps(compact_cols); aj = json.dumps(all_cols); dtc = detail_title_col
    css = ('<style>#{t} .ivy-desk {{width:100%;border-collapse:collapse;font-size:.83rem;border:1px solid #e2ece9;overflow:hidden;}}#{t} .ivy-desk th {{background:#1a6b5a;color:white;font-weight:600;font-size:.78rem;letter-spacing:.04em;text-transform:uppercase;padding:.65rem 1rem;text-align:left;}}#{t} .ivy-desk td {{padding:.5rem 1rem;border-bottom:1px solid #e2ece9;color:#1c2b27;font-size:.83rem;white-space:nowrap;}}#{t} .ivy-desk tr:nth-child(even) td {{background:#f0faf7;}}#{t} .ivy-desk tr:hover td {{background:#e8f5f1;cursor:pointer;}}#{t} .ivy-mob {{display:none;}}#{t} .ivy-ctbl {{width:100%;border-collapse:collapse;table-layout:fixed;}}#{t} .ivy-ctbl th {{background:#1a6b5a;color:white;font-size:.7rem;font-weight:600;padding:5px 4px;text-transform:uppercase;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}}#{t} .ivy-ctbl td {{padding:5px 4px;border-bottom:1px solid #e2ece9;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#1c2b27;font-size:.78rem;}}#{t} .ivy-ctbl tr:nth-child(even) td {{background:#f0faf7;}}#{t} .ivy-ctbl tr {{cursor:pointer;}}#{t} .ivy-ctbl tr:active td {{background:#e8f5f1;}}#{t} .ivy-hint {{text-align:center;font-size:.7rem;color:#9ab4ad;padding:4px 0 2px;}}#{t} .ivy-tip {{color:#9ab4ad;font-size:.7rem;}}#{t} .ivy-dtl {{display:none;}}#{t} .ivy-bk {{display:flex;align-items:center;gap:6px;background:#1a6b5a;color:white;border:none;padding:8px 12px;font-size:.8rem;font-weight:600;cursor:pointer;width:100%;}}#{t} .ivy-db {{padding:10px 10px 16px;background:#f7f9f8;}}#{t} .ivy-dt {{font-size:.85rem;font-weight:700;color:#1c2b27;margin-bottom:8px;word-break:break-word;}}#{t} .ivy-dr {{display:flex;justify-content:space-between;align-items:flex-start;padding:5px 0;border-bottom:1px solid #e2ece9;}}#{t} .ivy-dl {{font-size:.7rem;color:#5a7268;font-weight:600;text-transform:uppercase;letter-spacing:.04em;min-width:40%;padding-right:8px;}}#{t} .ivy-dv {{font-size:.78rem;color:#1c2b27;font-weight:500;text-align:right;word-break:break-word;}}#{t} .ivy-scroll {{overflow-x:auto;-webkit-overflow-scrolling:touch;}}#{t} .ivy-desk th:first-child, #{t} .ivy-desk td:first-child {{position:sticky;left:0;z-index:3;box-shadow:2px 0 4px rgba(0,0,0,0.06);}}#{t} .ivy-desk th:first-child {{background:#1a6b5a;z-index:4;}}#{t} .ivy-desk td:first-child {{background:#ffffff;}}#{t} .ivy-desk tr:nth-child(even) td:first-child {{background:#f0faf7;}}@media (max-width:768px) {{#{t} .ivy-desk {{display:none;}} #{t} .ivy-mob {{display:block;}} }}</style>').replace('{t}', table_id)
    body = ('<div id="{t}"><div class="ivy-scroll"><div class="ivy-desk"><table><thead><tr id="{t}_dh"></tr></thead><tbody id="{t}_db"></tbody></table></div></div><div class="ivy-mob"><div class="ivy-list" id="{t}_ls"><div class="ivy-hint">Tap any row for full details</div><table class="ivy-ctbl"><thead><tr id="{t}_mh"></tr></thead><tbody id="{t}_mb"></tbody></table></div><div class="ivy-dtl" id="{t}_dtl"><button class="ivy-bk" onclick="ivy_bk_{t}()">&#8592; Back</button><div class="ivy-db"><div class="ivy-dt" id="{t}_dtt"></div><div id="{t}_dr"></div></div></div></div></div>').replace('{t}', table_id)
    js = ('<script>(function(){var R={rj},C={cj},A={aj},T="{t}",D="{d}",W=window;var dh=document.getElementById(T+"_dh");A.forEach(function(c){var e=document.createElement("th");e.textContent=c;dh.appendChild(e);});var db=document.getElementById(T+"_db");R.forEach(function(r,i){var tr=document.createElement("tr");tr.style.cursor="pointer";A.forEach(function(c){var td=document.createElement("td");td.textContent=r[c]||"";tr.appendChild(td);});tr.onclick=function(){W["ivs_"+T](i);};db.appendChild(tr);});var mh=document.getElementById(T+"_mh");C.forEach(function(c){var e=document.createElement("th");e.textContent=c;mh.appendChild(e);});var te=document.createElement("th");te.style.width="14px";mh.appendChild(te);var mb=document.getElementById(T+"_mb");R.forEach(function(r,i){var tr=document.createElement("tr");C.forEach(function(c){var td=document.createElement("td");td.textContent=r[c]||"";tr.appendChild(td);});var ti=document.createElement("td");ti.innerHTML="<span class=\\"ivy-tip\\">&#8250;</span>";tr.appendChild(ti);tr.onclick=function(){W["ivs_"+T](i);};mb.appendChild(tr);});W["ivs_"+T]=function(i){var r=R[i];document.getElementById(T+"_dtt").textContent=r[D]||("Row "+(i+1));var dr=document.getElementById(T+"_dr");dr.innerHTML="";A.forEach(function(c){if(r[c]===""||r[c]==null)return;var d=document.createElement("div");d.className="ivy-dr";d.innerHTML="<span class=\\"ivy-dl\\">"+ c +"</span><span class=\\"ivy-dv\\">"+(r[c]||"\u2014")+"</span>";dr.appendChild(d);});document.getElementById(T+"_ls").style.display="none";document.getElementById(T+"_dtl").style.display="block";};W["ivy_bk_"+T]=function(){document.getElementById(T+"_dtl").style.display="none";document.getElementById(T+"_ls").style.display="block";};})();</script>').replace('{rj}', rj).replace('{cj}', cj).replace('{aj}', aj).replace('{t}', table_id).replace('{d}', dtc)
    return components.html(css + body + js, height=max(250, len(rows)*34+120), scrolling=True)


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

    # Build table data — flatten MultiIndex columns if present (e.g. pivot_table)
    df_out = df.reset_index()
    if isinstance(df_out.columns, pd.MultiIndex):
        df_out.columns = [
            " ".join(str(c) for c in col).strip() if isinstance(col, tuple) else str(col)
            for col in df_out.columns
        ]
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
        # Check if this user is a manager or senior_manager
        _ui = safe_exec(
            admin_supabase.table("users")
            .select("id, username, designation")
            .eq("id", current_user_id)
            .limit(1)
        )
        user_info = _ui[0] if _ui else {}
        designation = (user_info or {}).get("designation", "")
        is_manager = designation in ("manager", "senior_manager")

        if is_manager:
            reports = safe_exec(
                admin_supabase.table("users")
                .select("id, username")
                .eq("report_to", current_user_id)
                .eq("is_active", True)
            ) or []
            team = [{"id": current_user_id,
                     "username": (user_info or {}).get("username", "Me") + " (You)"}]
            team += reports
            sel_users = st.multiselect(
                "Select Team Member(s)", team,
                default=team,
                format_func=lambda x: x["username"],
                key=f"{key}_users",
            )
            sel_user_ids = [u["id"] for u in sel_users]
            st.caption(f"Manager view — {len(reports)} direct report(s) shown.")
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



def _is_cancelled_doc(d):
    """A payment/doc is cancelled if its narration starts with [CANCELLED]
    or its allocation_status is CANCELLED. Matches the Cancel Payment marker."""
    narr = (d.get("narration") or "")
    return narr.startswith("[CANCELLED]") or (d.get("allocation_status") == "CANCELLED")


# ─────────────────────────────────────────────────────────────────────────────
# REPORT 1 - Product x Month : Invoice qty | Credit Note qty  (per stockist)
# ─────────────────────────────────────────────────────────────────────────────

def _report1(role, user_id):
    st.markdown("#### Report 1 - Product x Month: Invoice & Credit Note Quantity")
    st.caption(
        "Rows = Products.  Columns = Month -> Invoice (Sale | Free | Total) | Credit Note.  "
        "Filter by User(s) -> Stockist(s)."
    )

    yf, mf, yt, mt = _period_selectors("r1")

    sel_user_ids, stockist_ids, stockist_label = _user_and_stockist_selectors(
        "r1", role, user_id
    )
    if not stockist_ids:
        return

    if not st.button("Generate Report 1", key="r1_btn", type="primary"):
        return

    with st.spinner("Fetching data..."):
        from_date = date(yf, mf, 1)
        to_date   = date(yt, 12, 31) if mt == 12 else date(yt, mt + 1, 1)
        periods   = _period_range(yf, mf, yt, mt)
        period_set = {(y, m) for y, m in periods}

        # Invoices: stockist is the recipient (to_entity_id)
        inv_docs = safe_exec(
            admin_supabase.table("ops_documents")
            .select("id, ops_date, stock_as, narration, allocation_status, to_entity_id")
            .eq("stock_as", "normal")
            .eq("is_deleted", False)
            .in_("to_entity_id", stockist_ids)
            .gte("ops_date", from_date.isoformat())
            .lt("ops_date", to_date.isoformat())
        ) or []

        # Credit notes: stockist is the source (from_entity_id)
        cn_docs = safe_exec(
            admin_supabase.table("ops_documents")
            .select("id, ops_date, stock_as, narration, allocation_status, from_entity_id")
            .eq("stock_as", "credit_note")
            .eq("is_deleted", False)
            .in_("from_entity_id", stockist_ids)
            .gte("ops_date", from_date.isoformat())
            .lt("ops_date", to_date.isoformat())
        ) or []

        # Drop cancelled, build id -> (period, kind)
        doc_info = {}
        for d in inv_docs:
            if _is_cancelled_doc(d):
                continue
            y, mo = int(d["ops_date"][:4]), int(d["ops_date"][5:7])
            if (y, mo) in period_set:
                doc_info[d["id"]] = ((y, mo), "Invoice")
        for d in cn_docs:
            if _is_cancelled_doc(d):
                continue
            y, mo = int(d["ops_date"][:4]), int(d["ops_date"][5:7])
            if (y, mo) in period_set:
                doc_info[d["id"]] = ((y, mo), "Credit Note")

        if not doc_info:
            st.info("No Invoice / Credit Note documents found for this period.")
            return

        doc_ids = list(doc_info.keys())

        # Lines (quantity) — chunk the .in_() to avoid oversized requests
        lines_raw = []
        for i in range(0, len(doc_ids), 100):
            batch = doc_ids[i:i + 100]
            lines_raw += safe_exec(
                admin_supabase.table("ops_lines")
                .select("ops_document_id, sale_qty, free_qty, product_id")
                .in_("ops_document_id", batch)
            ) or []

        if not lines_raw:
            st.info("No product lines found for the matching documents.")
            return

        # Product names
        prod_ids = list({ln["product_id"] for ln in lines_raw if ln.get("product_id")})
        prod_map = {}
        for i in range(0, len(prod_ids), 100):
            batch = prod_ids[i:i + 100]
            prows = safe_exec(
                admin_supabase.table("products").select("id, name").in_("id", batch)
            ) or []
            for p in prows:
                prod_map[p["id"]] = p["name"]

        # Aggregate: (product, period, column_label) -> qty
        # Invoice -> three measures: Inv-Sale, Inv-Free, Inv-Total
        # Credit Note -> single measure: CN (sale + free, i.e. total returned)
        agg = {}
        for ln in lines_raw:
            info = doc_info.get(ln["ops_document_id"])
            if not info:
                continue
            (y, mo), kind = info
            product = prod_map.get(ln.get("product_id"), "Unknown")
            sale = _safe_float(ln.get("sale_qty"))
            free = _safe_float(ln.get("free_qty"))
            if kind == "Invoice":
                for measure, val in (("Inv-Sale", sale),
                                     ("Inv-Free", free),
                                     ("Inv-Total", sale + free)):
                    k = (product, y, mo, measure)
                    agg[k] = agg.get(k, 0.0) + val
            else:  # Credit Note
                k = (product, y, mo, "CN")
                agg[k] = agg.get(k, 0.0) + (sale + free)

    if not agg:
        st.info("No data to display after aggregation.")
        return

    rows_list = [
        {"Product": p, "Period": _mlabel(y, mo), "Type": t, "Qty": v}
        for (p, y, mo, t), v in agg.items()
    ]
    df_raw = pd.DataFrame(rows_list)

    period_labels = [_mlabel(y, m) for y, m in periods]
    # Order within each month: Inv-Sale, Inv-Free, Inv-Total, then CN
    type_order    = ["Inv-Sale", "Inv-Free", "Inv-Total", "CN"]

    pivot = df_raw.pivot_table(
        index="Product", columns=["Period", "Type"],
        values="Qty", aggfunc="sum", fill_value=0,
    )
    ordered_cols = [
        (p, t) for p in period_labels for t in type_order
        if (p, t) in pivot.columns
    ]
    pivot = pivot.reindex(columns=ordered_cols, fill_value=0).astype(int)

    # Flatten for mobile table
    pivot_flat = pivot.copy()
    pivot_flat.columns = [' '.join(str(c) for c in col).strip() if isinstance(col, tuple) else str(col) for col in pivot_flat.columns]
    pivot_flat = pivot_flat.reset_index()
    first_col = pivot_flat.columns[0]
    _mobile_table(
        pivot_flat,
        compact_cols=[first_col] + list(pivot_flat.columns[1:4]),
        detail_title_col=first_col,
        uid_prefix="r1_pivot"
    )

    subtitle  = (f"Stockists: {stockist_label}  |  "
                 f"Period: {_mlabel(yf, mf)} - {_mlabel(yt, mt)}")
    pdf_bytes = _build_pdf("Report 1 - Product x Month (Invoice / Credit Note Qty)", subtitle, pivot)
    st.download_button(
        "Download PDF", data=pdf_bytes,
        file_name="r1_product_month_qty.pdf",
        mime="application/pdf", key="r1_pdf",
    )


# ─────────────────────────────────────────────────────────────────────────────
# SHARED ENGINE - Month-column financial matrix (Reports 2,4,5)
# Layout: rows = metrics, columns = months  (transposed)
# ─────────────────────────────────────────────────────────────────────────────

def _stockist_financial_matrix(key, role, user_id, row_specs, report_title):
    """
    row_specs: ordered list of (row_key, row_label).
    row_key values:
      INVOICE_GROSS | INVOICE_NET | CREDIT_NOTE |
      PAYMENT_GROSS | PAYMENT_DISCOUNT | PAYMENT_NET
    Months run across the columns. A TOTAL column is appended.
    Cancelled payments are excluded.
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
        period_set = {(y, m) for y, m in periods}
        row_keys = [rk for rk, _ in row_specs]

        need_invoice = any(k in row_keys for k in ("INVOICE_GROSS", "INVOICE_NET"))
        need_cn      = "CREDIT_NOTE" in row_keys
        need_payment = any(k in row_keys for k in ("PAYMENT_GROSS", "PAYMENT_DISCOUNT", "PAYMENT_NET"))

        agg = {(y, m): {rk: 0.0 for rk, _ in row_specs} for y, m in periods}

        # ---- Invoices (to_entity_id = stockist) ----
        if need_invoice:
            inv_docs = safe_exec(
                admin_supabase.table("ops_documents")
                .select("id, ops_date, stock_as, narration, allocation_status, invoice_total, to_entity_id")
                .eq("stock_as", "normal").eq("is_deleted", False)
                .in_("to_entity_id", stockist_ids)
                .gte("ops_date", from_date.isoformat())
                .lt("ops_date", to_date.isoformat())
            ) or []
            inv_docs = [d for d in inv_docs if not _is_cancelled_doc(d)]
            inv_ids  = [d["id"] for d in inv_docs]

            # GROSS = financial_ledger.debit (ONE true total per invoice).
            # ops_lines.gross_amount is the document total stamped on EVERY line,
            # so summing lines inflates by the product count (N products = N x).
            # NET = ops_documents.invoice_total (document-level, non-inflated).
            inv_gross = {}
            for i in range(0, len(inv_ids), 100):
                batch = inv_ids[i:i + 100]
                for row in (safe_exec(
                    admin_supabase.table("financial_ledger")
                    .select("ops_document_id, debit, created_at")
                    .in_("ops_document_id", batch)
                    .gt("debit", 0)
                    .order("created_at")
                ) or []):
                    oid = row["ops_document_id"]
                    if oid not in inv_gross:          # first debit row per invoice
                        inv_gross[oid] = _safe_float(row.get("debit"))
            for d in inv_docs:
                y, mo = int(d["ops_date"][:4]), int(d["ops_date"][5:7])
                if (y, mo) not in period_set:
                    continue
                if "INVOICE_GROSS" in row_keys:
                    g = inv_gross.get(d["id"], 0.0)
                    if g <= 0:
                        g = _safe_float(d.get("invoice_total"))
                    agg[(y, mo)]["INVOICE_GROSS"] += g
                if "INVOICE_NET" in row_keys:
                    agg[(y, mo)]["INVOICE_NET"] += _safe_float(d.get("invoice_total"))

        # ---- Credit notes (from_entity_id = stockist) ----
        # stock_as = "credit_note" catches BOTH stock-movement and financial-only
        # credit notes. The reliable amount is financial_ledger.credit (this is the
        # same figure that was previously (wrongly) landing in the Payment row).
        # Fall back to ops_lines.net_amount, then invoice_total, if no ledger row.
        if need_cn:
            cn_docs = safe_exec(
                admin_supabase.table("ops_documents")
                .select("id, ops_date, stock_as, narration, allocation_status, invoice_total, from_entity_id")
                .eq("stock_as", "credit_note").eq("is_deleted", False)
                .in_("from_entity_id", stockist_ids)
                .gte("ops_date", from_date.isoformat())
                .lt("ops_date", to_date.isoformat())
            ) or []
            cn_docs = [d for d in cn_docs if not _is_cancelled_doc(d)]
            cn_ids  = [d["id"] for d in cn_docs]

            # Primary source: financial_ledger.credit (one figure per CN)
            cn_ledger = {}
            for i in range(0, len(cn_ids), 100):
                batch = cn_ids[i:i + 100]
                for row in (safe_exec(
                    admin_supabase.table("financial_ledger")
                    .select("ops_document_id, credit")
                    .in_("ops_document_id", batch)
                ) or []):
                    oid = row["ops_document_id"]
                    cn_ledger[oid] = cn_ledger.get(oid, 0.0) + _safe_float(row.get("credit"))

            # Fallback source: ops_lines.net_amount. The same document total is
            # stamped on every line, so take MAX (the single true total), not SUM,
            # to avoid inflating by product count.
            cn_net = {}
            for i in range(0, len(cn_ids), 100):
                batch = cn_ids[i:i + 100]
                for ln in (safe_exec(
                    admin_supabase.table("ops_lines")
                    .select("ops_document_id, net_amount")
                    .in_("ops_document_id", batch)
                ) or []):
                    oid = ln["ops_document_id"]
                    val = _safe_float(ln.get("net_amount"))
                    cn_net[oid] = max(cn_net.get(oid, 0.0), val)

            for d in cn_docs:
                y, mo = int(d["ops_date"][:4]), int(d["ops_date"][5:7])
                if (y, mo) not in period_set:
                    continue
                amt = cn_ledger.get(d["id"], 0.0)
                if amt <= 0:
                    amt = cn_net.get(d["id"], 0.0)
                if amt <= 0:
                    amt = _safe_float(d.get("invoice_total"))
                agg[(y, mo)]["CREDIT_NOTE"] += amt

        # ---- Payments (from_entity_id = stockist, ops_type ADJUSTMENT) ----
        # IMPORTANT: a doc with stock_as = "credit_note" is ALWAYS a credit note,
        # even when its ops_type is ADJUSTMENT (financial-only credit notes).
        # Those must NOT count as payments — they belong only to the Credit Note row.
        if need_payment:
            pay_docs = safe_exec(
                admin_supabase.table("ops_documents")
                .select("id, ops_date, ops_type, stock_as, narration, allocation_status, from_entity_id")
                .eq("ops_type", "ADJUSTMENT").eq("is_deleted", False)
                .in_("from_entity_id", stockist_ids)
                .gte("ops_date", from_date.isoformat())
                .lt("ops_date", to_date.isoformat())
            ) or []
            # Exclude cancelled, REV-DEL reversals, AND any credit-note docs
            pay_docs = [d for d in pay_docs
                        if not _is_cancelled_doc(d)
                        and not (d.get("narration") or "").startswith("REV-DEL")
                        and (d.get("stock_as") or "") != "credit_note"]
            pay_ids  = [d["id"] for d in pay_docs]
            pay_amt  = {}  # ops_document_id -> {gross, discount, net}
            for i in range(0, len(pay_ids), 100):
                batch = pay_ids[i:i + 100]
                for row in (safe_exec(
                    admin_supabase.table("financial_ledger")
                    .select("ops_document_id, gross_amount, discount_amount, net_amount, credit")
                    .in_("ops_document_id", batch)
                ) or []):
                    oid = row["ops_document_id"]
                    rec = pay_amt.setdefault(oid, {"gross": 0.0, "discount": 0.0, "net": 0.0})
                    # Prefer explicit gross/discount/net; fall back to credit as net
                    g = _safe_float(row.get("gross_amount"))
                    dsc = _safe_float(row.get("discount_amount"))
                    n = _safe_float(row.get("net_amount"))
                    if g == 0 and n == 0:
                        n = _safe_float(row.get("credit"))
                    rec["gross"]    += g
                    rec["discount"] += dsc
                    rec["net"]      += n
            for d in pay_docs:
                y, mo = int(d["ops_date"][:4]), int(d["ops_date"][5:7])
                if (y, mo) not in period_set:
                    continue
                rec = pay_amt.get(d["id"], {"gross": 0.0, "discount": 0.0, "net": 0.0})
                if "PAYMENT_GROSS" in row_keys:
                    agg[(y, mo)]["PAYMENT_GROSS"] += rec["gross"] if rec["gross"] > 0 else rec["net"]
                if "PAYMENT_DISCOUNT" in row_keys:
                    agg[(y, mo)]["PAYMENT_DISCOUNT"] += rec["discount"]
                if "PAYMENT_NET" in row_keys:
                    agg[(y, mo)]["PAYMENT_NET"] += rec["net"]

    # Build DataFrame: rows = metrics, columns = months
    period_labels = [_mlabel(y, m) for y, m in periods]
    data = {}
    for rk, rl in row_specs:
        data[rl] = [round(agg[(y, m)][rk], 2) for y, m in periods]
    df = pd.DataFrame(data, index=period_labels).T  # metrics as rows, months as cols
    df.columns = period_labels
    df["TOTAL"] = df.sum(axis=1)

    df_display = df.reset_index().rename(columns={"index": "Metric"})
    first_col = df_display.columns[0]
    _mobile_table(
        df_display,
        compact_cols=[first_col] + list(df_display.columns[1:4]),
        detail_title_col=first_col,
        uid_prefix=key + '_mat'
    )

    subtitle  = (f"Stockists: {stockist_label}  |  "
                 f"Period: {_mlabel(yf, mf)} - {_mlabel(yt, mt)}")
    pdf_bytes = _build_pdf(report_title, subtitle, df)
    st.download_button(
        "Download PDF", data=pdf_bytes,
        file_name=f"{key}_matrix.pdf",
        mime="application/pdf", key=f"{key}_pdf",
    )


# ─────────────────────────────────────────────────────────────────────────────
# REPORT 2 - Payment & Credit Note (rows) x Month (cols)
# ─────────────────────────────────────────────────────────────────────────────

def _report2(role, user_id):
    st.markdown("#### Report 2 - Payment & Credit Note by Month")
    st.caption("Rows = Payment, Credit Note.  Columns = Months.")
    _stockist_financial_matrix(
        key="r2", role=role, user_id=user_id,
        row_specs=[("PAYMENT_NET", "Payment"), ("CREDIT_NOTE", "Credit Note")],
        report_title="Report 2 - Payment & Credit Note by Month",
    )


# ─────────────────────────────────────────────────────────────────────────────
# REPORT 4 - Gross Invoice & Credit Note (rows) x Month (cols)
# ─────────────────────────────────────────────────────────────────────────────

def _report4(role, user_id):
    st.markdown("#### Report 4 - Gross Invoice & Credit Note by Month")
    st.caption("Rows = Gross Invoice, Credit Note.  Columns = Months.")
    _stockist_financial_matrix(
        key="r4", role=role, user_id=user_id,
        row_specs=[("INVOICE_GROSS", "Gross Invoice"), ("CREDIT_NOTE", "Credit Note")],
        report_title="Report 4 - Gross Invoice & Credit Note by Month",
    )


# ─────────────────────────────────────────────────────────────────────────────
# REPORT 5 - Full financial picture (rows) x Month (cols)
# ─────────────────────────────────────────────────────────────────────────────

def _report5(role, user_id):
    st.markdown("#### Report 5 - Full Financial Summary by Month")
    st.caption(
        "Rows = Gross Invoice, Net Invoice, Credit Note, "
        "Payment (Gross), Discount, Payment (Net).  Columns = Months."
    )
    _stockist_financial_matrix(
        key="r5", role=role, user_id=user_id,
        row_specs=[
            ("INVOICE_GROSS",    "Gross Invoice"),
            ("INVOICE_NET",      "Net Invoice"),
            ("CREDIT_NOTE",      "Credit Note"),
            ("PAYMENT_GROSS",    "Payment (Gross)"),
            ("PAYMENT_DISCOUNT", "Discount"),
            ("PAYMENT_NET",      "Payment (Net)"),
        ],
        report_title="Report 5 - Full Financial Summary by Month",
    )


# ─────────────────────────────────────────────────────────────────────────────
# USER-ONLY SELECTOR (for R6) — multi-select incl. All; role-aware
# ─────────────────────────────────────────────────────────────────────────────

def _user_only_selector(key, role, current_user_id):
    """Returns (selected_user_ids, label). Admin sees all users; manager sees
    self + direct reports; plain user is scoped to self."""
    if role == "admin":
        all_users = _load_all_users()
        sel = st.multiselect(
            "Select User(s)", all_users, default=all_users,
            format_func=lambda x: x["username"], key=f"{key}_users",
        )
        ids = [u["id"] for u in sel]
        label = "All Users" if len(sel) == len(all_users) else ", ".join(u["username"] for u in sel[:3])
        if 0 < len(sel) - 3:
            label += f" +{len(sel) - 3} more"
        return ids, label

    _ui = safe_exec(
        admin_supabase.table("users")
        .select("id, username, designation")
        .eq("id", current_user_id).limit(1)
    )
    info = _ui[0] if _ui else {}
    if (info.get("designation") or "") in ("manager", "senior_manager"):
        reports = safe_exec(
            admin_supabase.table("users")
            .select("id, username")
            .eq("report_to", current_user_id).eq("is_active", True)
        ) or []
        team = [{"id": current_user_id, "username": (info.get("username") or "Me") + " (You)"}] + reports
        sel = st.multiselect(
            "Select Team Member(s)", team, default=team,
            format_func=lambda x: x["username"], key=f"{key}_users",
        )
        ids = [u["id"] for u in sel]
        st.caption(f"Manager view — {len(reports)} direct report(s).")
        return ids, ("All (You + Team)" if len(sel) == len(team) else f"{len(sel)} user(s)")

    st.caption("Showing your own movement.")
    return [current_user_id], (info.get("username") or "Me")


# ─────────────────────────────────────────────────────────────────────────────
# REPORT 6 - Stock Movement : Product (rows) x Month
#   Sub-cols: Saleable | Free | Sample | Lot | Credit Note |
#             Total (excl CN) | Net (excl CN minus CN)
#   Saleable/Free/CN  -> via the selected users' allotted stockists
#   Sample/Lot        -> directly to the selected users (Company/CNF -> User)
# ─────────────────────────────────────────────────────────────────────────────

def _report6(role, user_id):
    st.markdown("#### Report 6 - Stock Movement: Product x Month (by User)")
    st.caption(
        "Rows = Products.  Per month: Saleable | Free | Sample | Lot | "
        "Credit Note | Total (excl CN) | Net (Total − CN).  "
        "Saleable/Free/CN come from the user's allotted stockists; "
        "Sample/Lot come directly to the user."
    )

    yf, mf, yt, mt = _period_selectors("r6")

    sel_user_ids, user_label = _user_only_selector("r6", role, user_id)
    if not sel_user_ids:
        st.info("Select at least one user.")
        return

    # Allotted stockists across all selected users (deduplicated — Option A)
    avail_stockists = _load_stockists_for_users(sel_user_ids)
    stockist_ids = [s["id"] for s in avail_stockists]

    if not st.button("Generate Report 6", key="r6_btn", type="primary"):
        return

    with st.spinner("Fetching data..."):
        from_date = date(yf, mf, 1)
        to_date   = date(yt, 12, 31) if mt == 12 else date(yt, mt + 1, 1)
        periods   = _period_range(yf, mf, yt, mt)
        period_set = {(y, m) for y, m in periods}

        # ---- Invoices (saleable + free) — to the allotted stockists ----
        inv_docs = []
        if stockist_ids:
            inv_docs = safe_exec(
                admin_supabase.table("ops_documents")
                .select("id, ops_date, stock_as, narration, allocation_status, to_entity_id")
                .eq("stock_as", "normal").eq("is_deleted", False)
                .in_("to_entity_id", stockist_ids)
                .gte("ops_date", from_date.isoformat())
                .lt("ops_date", to_date.isoformat())
            ) or []
            inv_docs = [d for d in inv_docs if not _is_cancelled_doc(d)]

        # ---- Credit notes — from the allotted stockists ----
        cn_docs = []
        if stockist_ids:
            cn_docs = safe_exec(
                admin_supabase.table("ops_documents")
                .select("id, ops_date, stock_as, narration, allocation_status, from_entity_id")
                .eq("stock_as", "credit_note").eq("is_deleted", False)
                .in_("from_entity_id", stockist_ids)
                .gte("ops_date", from_date.isoformat())
                .lt("ops_date", to_date.isoformat())
            ) or []
            cn_docs = [d for d in cn_docs if not _is_cancelled_doc(d)]

        # ---- Samples & Lots — directly TO the selected users ----
        sl_docs = safe_exec(
            admin_supabase.table("ops_documents")
            .select("id, ops_date, stock_as, narration, allocation_status, to_entity_id")
            .in_("stock_as", ["sample", "lot"]).eq("is_deleted", False)
            .in_("to_entity_id", sel_user_ids)
            .gte("ops_date", from_date.isoformat())
            .lt("ops_date", to_date.isoformat())
        ) or []
        sl_docs = [d for d in sl_docs if not _is_cancelled_doc(d)]

        # Map each doc id -> (period, kind)
        doc_kind = {}
        for d in inv_docs:
            y, mo = int(d["ops_date"][:4]), int(d["ops_date"][5:7])
            if (y, mo) in period_set:
                doc_kind[d["id"]] = ((y, mo), "INVOICE")
        for d in cn_docs:
            y, mo = int(d["ops_date"][:4]), int(d["ops_date"][5:7])
            if (y, mo) in period_set:
                doc_kind[d["id"]] = ((y, mo), "CN")
        for d in sl_docs:
            y, mo = int(d["ops_date"][:4]), int(d["ops_date"][5:7])
            if (y, mo) in period_set:
                doc_kind[d["id"]] = ((y, mo), (d.get("stock_as") or "").upper())  # SAMPLE / LOT

        if not doc_kind:
            st.info("No stock movement found for this period.")
            return

        all_ids = list(doc_kind.keys())

        # Lines — chunked
        lines_raw = []
        for i in range(0, len(all_ids), 100):
            batch = all_ids[i:i + 100]
            lines_raw += safe_exec(
                admin_supabase.table("ops_lines")
                .select("ops_document_id, sale_qty, free_qty, product_id")
                .in_("ops_document_id", batch)
            ) or []

        if not lines_raw:
            st.info("No product lines found for the matching documents.")
            return

        # Product names
        prod_ids = list({ln["product_id"] for ln in lines_raw if ln.get("product_id")})
        prod_map = {}
        for i in range(0, len(prod_ids), 100):
            batch = prod_ids[i:i + 100]
            for p in (safe_exec(
                admin_supabase.table("products").select("id, name").in_("id", batch)
            ) or []):
                prod_map[p["id"]] = p["name"]

        # Aggregate: (product, period, measure) -> qty
        agg = {}
        def _add(product, ym, measure, val):
            k = (product, ym, measure)
            agg[k] = agg.get(k, 0.0) + val

        for ln in lines_raw:
            info = doc_kind.get(ln["ops_document_id"])
            if not info:
                continue
            ym, kind = info
            product = prod_map.get(ln.get("product_id"), "Unknown")
            sale = _safe_float(ln.get("sale_qty"))
            free = _safe_float(ln.get("free_qty"))
            if kind == "INVOICE":
                _add(product, ym, "Saleable", sale)
                _add(product, ym, "Free", free)
            elif kind == "SAMPLE":
                _add(product, ym, "Sample", sale)        # sample/lot has no free
            elif kind == "LOT":
                _add(product, ym, "Lot", sale)
            elif kind == "CN":
                _add(product, ym, "CreditNote", sale + free)

    if not agg:
        st.info("No data to display after aggregation.")
        return

    # Build per-(product, period) measure dict, then compute totals
    measures = ["Saleable", "Free", "Sample", "Lot", "CreditNote"]
    cell = {}  # (product, period_label) -> {measure: qty}
    products = set()
    for (product, (y, mo), measure), val in agg.items():
        plabel = _mlabel(y, mo)
        products.add(product)
        cell.setdefault((product, plabel), {m: 0.0 for m in measures})
        cell[(product, plabel)][measure] += val

    period_labels = [_mlabel(y, m) for y, m in periods]
    # Column order per month
    sub_order = ["Saleable", "Free", "Sample", "Lot", "Credit Note",
                 "Total (excl CN)", "Net"]

    # Build a flat row per product with all month*subcol values
    rows = []
    for product in sorted(products):
        row = {"Product": product}
        for plabel in period_labels:
            c = cell.get((product, plabel), {m: 0.0 for m in measures})
            total_excl = c["Saleable"] + c["Free"] + c["Sample"] + c["Lot"]
            net = total_excl - c["CreditNote"]
            vals = {
                "Saleable":        c["Saleable"],
                "Free":            c["Free"],
                "Sample":          c["Sample"],
                "Lot":             c["Lot"],
                "Credit Note":     c["CreditNote"],
                "Total (excl CN)": total_excl,
                "Net":             net,
            }
            for sub in sub_order:
                row[f"{plabel} {sub}"] = int(vals[sub])
        rows.append(row)

    df = pd.DataFrame(rows)

    _mobile_table(
        df,
        compact_cols=[df.columns[0]] + list(df.columns[1:4]),
        detail_title_col=df.columns[0],
        uid_prefix="r6_move"
    )

    subtitle = (f"Users: {user_label}  |  Stockists allotted: {len(stockist_ids)}  |  "
                f"Period: {_mlabel(yf, mf)} - {_mlabel(yt, mt)}")
    # PDF uses the same flat frame (Product as index)
    pdf_bytes = _build_pdf("Report 6 - Stock Movement (by User)", subtitle, df.set_index("Product"))
    st.download_button(
        "Download PDF", data=pdf_bytes,
        file_name="r6_stock_movement.pdf",
        mime="application/pdf", key="r6_pdf",
    )


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def run_ops_reports():
    """Entry point. Renders sub-tabs inside the OPS Reports tab."""
    user_id = st.session_state.auth_user.id
    role    = st.session_state.get("role", "user")

    st.markdown("##### OPS matrix reports drawn from invoices, payments, credit notes, samples and lots.")
    if role != "admin":
        st.caption("You can see data for your own stockists only.")

    tabs = st.tabs([
        "R1 - Product x Month",
        "R2 - Payment & Credit Note",
        "R4 - Gross Invoice & Credit Note",
        "R5 - Full Financial Summary",
        "R6 - Stock Movement",
    ])

    with tabs[0]:
        _report1(role, user_id)
    with tabs[1]:
        _report2(role, user_id)
    with tabs[2]:
        _report4(role, user_id)
    with tabs[3]:
        _report5(role, user_id)
    with tabs[4]:
        _report6(role, user_id)

