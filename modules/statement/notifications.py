"""
Notifications Module — Admin Only
Reads from audit_logs table and displays a human-readable activity feed.
"""

import streamlit as st
from datetime import datetime, timezone
from anchors.supabase_client import admin_supabase


# ── Human-readable labels for every action ────────────────────
ACTION_CONFIG = {
    # Statement
    "statement_submitted":        ("📦", "Statement Submitted",        "green"),
    "reset_statement":            ("🔄", "Statement Reset",            "orange"),
    "admin_corrected_statement":  ("✏️",  "Statement Corrected",        "blue"),
    "delete_statement":           ("🗑️",  "Statement Deleted",          "red"),
    "create_stockist":            ("🏪", "Stockist Created",           "green"),
    "update_user":                ("👤", "User Updated",               "blue"),
    "create_territory":           ("📍", "Territory Created",          "green"),
    "update_territory":           ("📍", "Territory Updated",          "blue"),
    "reset_user_password":        ("🔐", "Password Reset",             "orange"),
    # OPS
    "CANCEL_INVOICE":             ("❌", "Invoice Cancelled",          "red"),
    "DELETE_INVOICE":             ("🗑️",  "Invoice Deleted",            "red"),
    "DELETE_OPS":                 ("🗑️",  "OPS Document Deleted",       "red"),
    "EDIT_INVOICE":               ("✏️",  "Invoice Edited",             "blue"),
    "DELETE_PAYMENT":             ("🗑️",  "Payment Deleted",            "red"),
    "DELETE_FREIGHT":             ("🗑️",  "Freight Deleted",            "red"),
    "DELETE_RETURN_REPLACE":      ("🗑️",  "Return/Replace Deleted",     "red"),
    "CREATE_FREIGHT":             ("🚚", "Freight Created",            "green"),
    "ALLOCATE_PAYMENT":           ("💰", "Payment Allocated",          "green"),
    # DCR
    "DCR_SUBMITTED":              ("📞", "DCR Submitted",              "green"),
    "DCR_DELETED":                ("🗑️",  "DCR Deleted",               "red"),
    # Tour
    "TOUR_CREATED":               ("🗓️",  "Tour Programme Created",     "green"),
    "TOUR_UPDATED":               ("✏️",  "Tour Programme Updated",     "blue"),
    "TOUR_DELETED":               ("🗑️",  "Tour Programme Deleted",     "red"),
    "TOUR_APPROVED":              ("✅", "Tour Programme Approved",    "green"),
    "TOUR_REJECTED":              ("❌", "Tour Programme Rejected",    "red"),
    # POB
    "POB_CREATED":                ("📋", "POB Document Created",       "green"),
    "POB_SUBMITTED":              ("📋", "POB Document Submitted",     "blue"),
    "POB_APPROVED":               ("✅", "POB Document Approved",      "green"),
    "POB_REJECTED":               ("❌", "POB Document Rejected",      "red"),
}

COLOR_MAP = {
    "green":  "#1a6b5a",
    "blue":   "#1a4b8a",
    "orange": "#b35c00",
    "red":    "#c0392b",
    "gray":   "#666666",
}


def _time_ago(dt_str):
    """Convert ISO datetime string to human-readable 'X ago' format."""
    if not dt_str:
        return "Unknown time"
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = now - dt
        seconds = int(diff.total_seconds())

        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            m = seconds // 60
            return f"{m} minute{'s' if m > 1 else ''} ago"
        elif seconds < 86400:
            h = seconds // 3600
            return f"{h} hour{'s' if h > 1 else ''} ago"
        elif seconds < 604800:
            d = seconds // 86400
            return f"{d} day{'s' if d > 1 else ''} ago"
        else:
            return dt.strftime("%d %b %Y")
    except Exception:
        return dt_str[:10] if dt_str else "Unknown"


def _get_username(user_id):
    """Fetch username from users table."""
    if not user_id:
        return "Unknown"
    try:
        result = admin_supabase.table("users").select("username").eq("id", str(user_id)).limit(1).execute()
        if result.data:
            return result.data[0]["username"]
    except Exception:
        pass
    return "Unknown"


def run_notifications():
    """Main notifications page — admin only."""

    st.title("🔔 Notifications")
    st.caption("All activity across the app — newest first")

    # ── Filters ───────────────────────────────────────────────────
    col1, col2, col3 = st.columns([2, 2, 1])

    with col1:
        module_options = {
            "All Modules": None,
            "📦 Statement": ["statement_submitted", "reset_statement", "admin_corrected_statement",
                             "delete_statement", "create_stockist", "update_user",
                             "create_territory", "update_territory", "reset_user_password"],
            "📥 OPS":       ["CANCEL_INVOICE", "DELETE_INVOICE", "DELETE_OPS", "EDIT_INVOICE",
                             "DELETE_PAYMENT", "DELETE_FREIGHT", "DELETE_RETURN_REPLACE",
                             "CREATE_FREIGHT", "ALLOCATE_PAYMENT"],
            "📞 DCR":       ["DCR_SUBMITTED", "DCR_DELETED"],
            "🗓️ Tour":      ["TOUR_CREATED", "TOUR_UPDATED", "TOUR_DELETED", "TOUR_APPROVED", "TOUR_REJECTED"],
            "📋 POB":       ["POB_CREATED", "POB_SUBMITTED", "POB_APPROVED", "POB_REJECTED"],
        }
        selected_module = st.selectbox("Filter by Module", list(module_options.keys()), key="notif_module_filter")

    with col2:
        limit_options = {"Last 50": 50, "Last 100": 100, "Last 200": 200, "All": 500}
        selected_limit = st.selectbox("Show", list(limit_options.keys()), key="notif_limit")

    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()

    st.divider()

    # ── Fetch from audit_logs ─────────────────────────────────────
    try:
        query = admin_supabase.table("audit_logs") \
            .select("id, action, message, performed_by, target_type, target_id, metadata, created_at") \
            .order("created_at", desc=True) \
            .limit(limit_options[selected_limit])

        result = query.execute()
        logs = result.data or []

    except Exception as e:
        st.error(f"❌ Could not load notifications: {e}")
        return

    if not logs:
        st.info("No activity recorded yet. Actions across the app will appear here.")
        return

    # ── Filter by module ──────────────────────────────────────────
    action_filter = module_options[selected_module]
    if action_filter:
        logs = [log for log in logs if log.get("action") in action_filter]

    if not logs:
        st.info(f"No activity found for {selected_module}.")
        return

    # ── Cache usernames to avoid repeated DB calls ────────────────
    user_cache = {}

    def get_username_cached(user_id):
        if not user_id:
            return "System"
        if user_id not in user_cache:
            user_cache[user_id] = _get_username(user_id)
        return user_cache[user_id]

    # ── Render feed ───────────────────────────────────────────────
    st.markdown(f"**{len(logs)} notification{'s' if len(logs) != 1 else ''}**")
    st.markdown("")

    for log in logs:
        action = log.get("action", "")
        message = log.get("message", "")
        performed_by = log.get("performed_by")
        created_at = log.get("created_at", "")
        metadata = log.get("metadata") or {}

        # Get config for this action
        config = ACTION_CONFIG.get(action)
        if config:
            emoji, label, color_key = config
        else:
            emoji, label, color_key = "📝", action.replace("_", " ").title(), "gray"

        color = COLOR_MAP.get(color_key, "#666666")
        username = get_username_cached(performed_by)

        # Try to get username from metadata if available
        if metadata.get("performed_by_username"):
            username = metadata["performed_by_username"]

        time_str = _time_ago(created_at)
        date_str = created_at[:10] if created_at else ""

        # Render notification card
        st.markdown(f"""
        <div style="
            background: white;
            border: 1px solid #e2ece9;
            border-left: 4px solid {color};
            border-radius: 8px;
            padding: 0.75rem 1rem;
            margin-bottom: 0.5rem;
            display: flex;
            align-items: flex-start;
            gap: 0.75rem;
        ">
            <div style="font-size: 1.4rem; line-height: 1; margin-top: 2px;">{emoji}</div>
            <div style="flex: 1; min-width: 0;">
                <div style="
                    font-weight: 600;
                    font-size: 0.88rem;
                    color: {color};
                    margin-bottom: 2px;
                ">{label}</div>
                <div style="
                    font-size: 0.92rem;
                    color: #1c2b27;
                    margin-bottom: 4px;
                ">{message}</div>
                <div style="
                    font-size: 0.78rem;
                    color: #5a7268;
                ">👤 <b>{username}</b> &nbsp;·&nbsp; 🕐 {time_str} &nbsp;·&nbsp; 📅 {date_str}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
