"""
Ivy Pharmaceuticals — UI Styling
Top navigation bar replacing sidebar — works on mobile + desktop
"""

IVY_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&display=swap');

:root {
    --ivy-green:        #1a6b5a;
    --ivy-green-light:  #e8f5f1;
    --ivy-green-mid:    #2d9b7f;
    --ivy-accent:       #f0faf7;
    --ivy-white:        #ffffff;
    --ivy-bg:           #f7f9f8;
    --ivy-border:       #e2ece9;
    --ivy-text:         #1c2b27;
    --ivy-text-soft:    #5a7268;
    --ivy-text-muted:   #9ab4ad;
    --ivy-danger:       #c0392b;
    --ivy-warning:      #e67e22;
    --ivy-shadow:       0 2px 12px rgba(26,107,90,0.08);
    --ivy-radius:       12px;
    --ivy-radius-sm:    8px;
    --ivy-font:         'DM Sans', sans-serif;
    --ivy-mono:         'DM Mono', monospace;
}

html, body, [class*="css"] {
    font-family: var(--ivy-font) !important;
    color: var(--ivy-text) !important;
}

.stApp { background-color: var(--ivy-bg) !important; }

/* ── HIDE SIDEBAR COMPLETELY ─────────────────── */
[data-testid="stSidebar"] { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }

/* ── MAIN CONTENT — push down for top nav ────── */
.main .block-container {
    padding: 1rem 1.5rem 3rem 1.5rem !important;
    max-width: 1200px !important;
    margin-top: 0 !important;
}

/* ── HEADINGS ────────────────────────────────── */
h1 { font-size: 1.6rem !important; font-weight: 700 !important; letter-spacing: -0.02em !important; }
h2 { font-size: 1.25rem !important; font-weight: 600 !important; }
h3 { font-size: 1rem !important; font-weight: 600 !important; }

@media (max-width: 768px) {
    h1 { font-size: 1.2rem !important; }
    h2 { font-size: 1rem !important; }
    h3 { font-size: 0.9rem !important; }
    .main .block-container {
        padding: 0.8rem 0.6rem 2rem 0.6rem !important;
    }
}

/* ── BUTTONS ─────────────────────────────────── */
.stButton > button[kind="primary"] {
    background: var(--ivy-green) !important;
    color: white !important;
    border: none !important;
    border-radius: var(--ivy-radius-sm) !important;
    font-weight: 600 !important;
    padding: 0.6rem 1.4rem !important;
    box-shadow: 0 2px 8px rgba(26,107,90,0.25) !important;
    transition: all 0.15s ease !important;
}
.stButton > button[kind="primary"]:hover {
    background: var(--ivy-green-mid) !important;
    transform: translateY(-1px) !important;
}
.stButton > button {
    background: var(--ivy-white) !important;
    color: var(--ivy-text) !important;
    border: 1.5px solid var(--ivy-border) !important;
    border-radius: var(--ivy-radius-sm) !important;
    font-weight: 500 !important;
    font-size: 0.88rem !important;
    padding: 0.5rem 1.2rem !important;
    transition: all 0.15s ease !important;
}
.stButton > button:hover {
    border-color: var(--ivy-green) !important;
    color: var(--ivy-green) !important;
}

@media (max-width: 768px) {
    .stButton > button {
        width: 100% !important;
        min-height: 48px !important;
        font-size: 0.95rem !important;
    }
}

/* ── INPUTS ──────────────────────────────────── */
.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stTextArea > div > div > textarea {
    border: 1.5px solid var(--ivy-border) !important;
    border-radius: var(--ivy-radius-sm) !important;
    background: var(--ivy-white) !important;
    font-family: var(--ivy-font) !important;
    font-size: 0.92rem !important;
}
.stTextInput > div > div > input:focus,
.stNumberInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: var(--ivy-green) !important;
    box-shadow: 0 0 0 3px rgba(26,107,90,0.1) !important;
}
.stTextInput label, .stNumberInput label, .stTextArea label,
.stSelectbox label, .stMultiSelect label, .stRadio label,
.stCheckbox label, .stDateInput label {
    font-size: 0.85rem !important;
    font-weight: 500 !important;
    color: var(--ivy-text-soft) !important;
}
@media (max-width: 768px) {
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input {
        font-size: 1rem !important;
        min-height: 48px !important;
    }
}

/* ── TABLES ──────────────────────────────────── */
.stDataFrame {
    border: 1px solid var(--ivy-border) !important;
    border-radius: var(--ivy-radius) !important;
    overflow: hidden !important;
    box-shadow: var(--ivy-shadow) !important;
}
.stDataFrame thead th {
    background: var(--ivy-green) !important;
    color: white !important;
    font-weight: 600 !important;
    font-size: 0.78rem !important;
    letter-spacing: 0.04em !important;
    text-transform: uppercase !important;
    padding: 0.65rem 1rem !important;
    position: sticky !important;
    top: 0 !important;
    z-index: 2 !important;
}
.stDataFrame tbody tr:nth-child(even) { background: var(--ivy-accent) !important; }
.stDataFrame tbody tr:hover { background: var(--ivy-green-light) !important; }
.stDataFrame tbody td {
    padding: 0.5rem 1rem !important;
    border-bottom: 1px solid var(--ivy-border) !important;
    font-size: 0.83rem !important;
}
@media (max-width: 768px) {
    .stDataFrame { overflow-x: auto !important; }
    .stDataFrame table { font-size: 0.72rem !important; }
    .stDataFrame tbody td,
    .stDataFrame thead th { padding: 0.4rem 0.5rem !important; }
}

/* ── METRICS ─────────────────────────────────── */
[data-testid="metric-container"] {
    background: var(--ivy-white) !important;
    border: 1px solid var(--ivy-border) !important;
    border-radius: var(--ivy-radius) !important;
    padding: 1rem 1.2rem !important;
    box-shadow: var(--ivy-shadow) !important;
}
[data-testid="metric-container"] [data-testid="stMetricLabel"] {
    font-size: 0.75rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.05em !important;
    text-transform: uppercase !important;
    color: var(--ivy-text-soft) !important;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-size: 1.5rem !important;
    font-weight: 700 !important;
    color: var(--ivy-green) !important;
}

/* ── TABS ────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    background: var(--ivy-white) !important;
    border-bottom: 2px solid var(--ivy-border) !important;
}
.stTabs [data-baseweb="tab"] {
    font-size: 0.88rem !important;
    font-weight: 500 !important;
    color: var(--ivy-text-soft) !important;
    padding: 0.65rem 1.1rem !important;
}
.stTabs [aria-selected="true"] {
    color: var(--ivy-green) !important;
    border-bottom: 2px solid var(--ivy-green) !important;
    font-weight: 600 !important;
    background: var(--ivy-green-light) !important;
}

/* ── SCROLLBAR ───────────────────────────────── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--ivy-bg); }
::-webkit-scrollbar-thumb { background: var(--ivy-border); border-radius: 3px; }

/* ── DIVIDERS ────────────────────────────────── */
hr {
    border: none !important;
    border-top: 1px solid var(--ivy-border) !important;
    margin: 1.2rem 0 !important;
}

/* ── ALERTS ──────────────────────────────────── */
.stAlert {
    border-radius: var(--ivy-radius-sm) !important;
    font-size: 0.88rem !important;
}

/* ── HIDE STREAMLIT BRANDING ─────────────────── */
#MainMenu { visibility: hidden !important; }
footer { visibility: hidden !important; }
[data-testid="stToolbar"] { display: none !important; }
header[data-testid="stHeader"] { display: none !important; }

/* ── TOP NAV BAR ─────────────────────────────── */
.ivy-topnav {
    position: sticky;
    top: 0;
    left: 0;
    right: 0;
    z-index: 9999;
    background: var(--ivy-white);
    border-bottom: 1px solid var(--ivy-border);
    box-shadow: 0 2px 12px rgba(26,107,90,0.08);
    margin-bottom: 1rem;
}

.ivy-topnav-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.6rem 1.2rem;
    background: var(--ivy-green);
    color: white;
}

.ivy-topnav-header .app-title {
    font-size: 1rem;
    font-weight: 700;
    letter-spacing: 0.01em;
    color: white;
}

.ivy-topnav-header .user-info {
    font-size: 0.78rem;
    opacity: 0.85;
    color: white;
}

.ivy-topnav-buttons {
    display: flex;
    overflow-x: auto;
    gap: 2px;
    padding: 4px 6px;
    scrollbar-width: none;
    -webkit-overflow-scrolling: touch;
    background: var(--ivy-white);
}

.ivy-topnav-buttons::-webkit-scrollbar { display: none; }

/* Style the Streamlit buttons inside topnav */
.ivy-topnav-buttons .stButton > button {
    white-space: nowrap !important;
    min-width: fit-content !important;
    width: auto !important;
    padding: 0.35rem 0.8rem !important;
    font-size: 0.78rem !important;
    font-weight: 500 !important;
    border: 1px solid var(--ivy-border) !important;
    border-radius: 20px !important;
    background: var(--ivy-white) !important;
    color: var(--ivy-text) !important;
    box-shadow: none !important;
    min-height: 32px !important;
    transition: all 0.15s ease !important;
}

.ivy-topnav-buttons .stButton > button:hover {
    background: var(--ivy-green-light) !important;
    border-color: var(--ivy-green) !important;
    color: var(--ivy-green) !important;
}

/* Logout button in topnav — red pill */
.ivy-topnav-logout .stButton > button {
    white-space: nowrap !important;
    min-width: fit-content !important;
    width: auto !important;
    padding: 0.35rem 0.8rem !important;
    font-size: 0.78rem !important;
    font-weight: 500 !important;
    border: 1px solid #fad7d4 !important;
    border-radius: 20px !important;
    background: #fff5f5 !important;
    color: var(--ivy-danger) !important;
    box-shadow: none !important;
    min-height: 32px !important;
}

/* Statement sidebar replacement — shown as card above content */
.ivy-stmt-nav .stButton > button {
    width: 100% !important;
    text-align: left !important;
    background: var(--ivy-white) !important;
    border: 1px solid var(--ivy-border) !important;
    border-radius: var(--ivy-radius-sm) !important;
    padding: 0.5rem 0.8rem !important;
    font-size: 0.85rem !important;
    margin-bottom: 4px !important;
    box-shadow: none !important;
}
.ivy-stmt-nav .stButton > button:hover {
    background: var(--ivy-green-light) !important;
    border-color: var(--ivy-green) !important;
    color: var(--ivy-green) !important;
}

</style>
"""


def apply_styles():
    """Apply all Ivy Pharmaceuticals styles."""
    import streamlit as st
    st.markdown(IVY_CSS, unsafe_allow_html=True)
