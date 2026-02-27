"""
Ivy Pharmaceuticals — UI Styling
Apply this in app.py via: apply_styles()
Clean & Professional theme — optimised for mobile + desktop
"""

IVY_CSS = """
<style>
/* ═══════════════════════════════════════════════
   FONTS
═══════════════════════════════════════════════ */
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&display=swap');

/* ═══════════════════════════════════════════════
   ROOT VARIABLES
═══════════════════════════════════════════════ */
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
    --ivy-success:      #1a6b5a;
    --ivy-shadow:       0 2px 12px rgba(26,107,90,0.08);
    --ivy-radius:       12px;
    --ivy-radius-sm:    8px;
    --ivy-font:         'DM Sans', sans-serif;
    --ivy-mono:         'DM Mono', monospace;
}

/* ═══════════════════════════════════════════════
   GLOBAL BASE
═══════════════════════════════════════════════ */
html, body, [class*="css"] {
    font-family: var(--ivy-font) !important;
    color: var(--ivy-text) !important;
}

.stApp {
    background-color: var(--ivy-bg) !important;
}

/* ═══════════════════════════════════════════════
   SIDEBAR
═══════════════════════════════════════════════ */
[data-testid="stSidebar"] {
    background: var(--ivy-white) !important;
    border-right: 1px solid var(--ivy-border) !important;
    box-shadow: 2px 0 16px rgba(26,107,90,0.06) !important;
}

[data-testid="stSidebar"] > div:first-child {
    padding: 1.5rem 1rem !important;
}

/* Sidebar title */
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    font-size: 0.8rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
    color: var(--ivy-text-muted) !important;
    margin-top: 1.2rem !important;
    margin-bottom: 0.4rem !important;
}

/* Sidebar buttons */
[data-testid="stSidebar"] .stButton > button {
    width: 100% !important;
    text-align: left !important;
    background: transparent !important;
    border: none !important;
    border-radius: var(--ivy-radius-sm) !important;
    color: var(--ivy-text) !important;
    font-size: 0.9rem !important;
    font-weight: 400 !important;
    padding: 0.55rem 0.8rem !important;
    margin-bottom: 2px !important;
    transition: all 0.15s ease !important;
    box-shadow: none !important;
}

[data-testid="stSidebar"] .stButton > button:hover {
    background: var(--ivy-green-light) !important;
    color: var(--ivy-green) !important;
    font-weight: 500 !important;
    transform: translateX(3px) !important;
}

/* Logout button — distinct */
[data-testid="stSidebar"] .stButton > button[kind="secondary"] {
    color: var(--ivy-danger) !important;
    margin-top: 0.5rem !important;
}

[data-testid="stSidebar"] .stButton > button[kind="secondary"]:hover {
    background: #fdf0ef !important;
    color: var(--ivy-danger) !important;
}

/* Sidebar caption/text */
[data-testid="stSidebar"] .stCaption,
[data-testid="stSidebar"] p {
    font-size: 0.82rem !important;
    color: var(--ivy-text-soft) !important;
}

/* Sidebar divider */
[data-testid="stSidebar"] hr {
    border-color: var(--ivy-border) !important;
    margin: 0.8rem 0 !important;
}

/* ═══════════════════════════════════════════════
   MAIN CONTENT AREA
═══════════════════════════════════════════════ */
.main .block-container {
    padding: 2rem 2rem 4rem 2rem !important;
    max-width: 1100px !important;
}

/* Mobile padding */
@media (max-width: 768px) {
    .main .block-container {
        padding: 1rem 0.8rem 4rem 0.8rem !important;
    }
}

/* ═══════════════════════════════════════════════
   HEADINGS
═══════════════════════════════════════════════ */
h1 {
    font-size: 1.7rem !important;
    font-weight: 700 !important;
    color: var(--ivy-text) !important;
    letter-spacing: -0.02em !important;
    margin-bottom: 0.2rem !important;
}

h2 {
    font-size: 1.3rem !important;
    font-weight: 600 !important;
    color: var(--ivy-text) !important;
}

h3 {
    font-size: 1.05rem !important;
    font-weight: 600 !important;
    color: var(--ivy-text) !important;
}

@media (max-width: 768px) {
    h1 { font-size: 1.3rem !important; }
    h2 { font-size: 1.1rem !important; }
    h3 { font-size: 0.95rem !important; }
}

/* ═══════════════════════════════════════════════
   BUTTONS — PRIMARY
═══════════════════════════════════════════════ */
.stButton > button[kind="primary"],
.stButton > button[data-testid="baseButton-primary"] {
    background: var(--ivy-green) !important;
    color: white !important;
    border: none !important;
    border-radius: var(--ivy-radius-sm) !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    padding: 0.6rem 1.4rem !important;
    transition: all 0.15s ease !important;
    box-shadow: 0 2px 8px rgba(26,107,90,0.25) !important;
    letter-spacing: 0.01em !important;
}

.stButton > button[kind="primary"]:hover {
    background: var(--ivy-green-mid) !important;
    box-shadow: 0 4px 16px rgba(26,107,90,0.35) !important;
    transform: translateY(-1px) !important;
}

/* Secondary buttons */
.stButton > button[kind="secondary"],
.stButton > button {
    background: var(--ivy-white) !important;
    color: var(--ivy-text) !important;
    border: 1.5px solid var(--ivy-border) !important;
    border-radius: var(--ivy-radius-sm) !important;
    font-weight: 500 !important;
    font-size: 0.88rem !important;
    padding: 0.5rem 1.2rem !important;
    transition: all 0.15s ease !important;
    box-shadow: var(--ivy-shadow) !important;
}

.stButton > button:hover {
    border-color: var(--ivy-green) !important;
    color: var(--ivy-green) !important;
    transform: translateY(-1px) !important;
}

/* Mobile — full width buttons */
@media (max-width: 768px) {
    .stButton > button {
        width: 100% !important;
        padding: 0.7rem 1rem !important;
        font-size: 0.95rem !important;
    }
}

/* ═══════════════════════════════════════════════
   FORM INPUTS
═══════════════════════════════════════════════ */
.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div,
.stMultiSelect > div > div {
    border: 1.5px solid var(--ivy-border) !important;
    border-radius: var(--ivy-radius-sm) !important;
    background: var(--ivy-white) !important;
    font-family: var(--ivy-font) !important;
    font-size: 0.92rem !important;
    color: var(--ivy-text) !important;
    transition: border-color 0.15s ease !important;
    padding: 0.5rem 0.8rem !important;
}

.stTextInput > div > div > input:focus,
.stNumberInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: var(--ivy-green) !important;
    box-shadow: 0 0 0 3px rgba(26,107,90,0.1) !important;
    outline: none !important;
}

/* Input labels */
.stTextInput label,
.stNumberInput label,
.stTextArea label,
.stSelectbox label,
.stMultiSelect label,
.stRadio label,
.stCheckbox label,
.stDateInput label {
    font-size: 0.85rem !important;
    font-weight: 500 !important;
    color: var(--ivy-text-soft) !important;
    margin-bottom: 4px !important;
}

/* Mobile inputs — bigger touch targets */
@media (max-width: 768px) {
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stSelectbox > div > div {
        font-size: 1rem !important;
        padding: 0.65rem 0.9rem !important;
        min-height: 44px !important;
    }
}

/* ═══════════════════════════════════════════════
   DATAFRAMES / TABLES
═══════════════════════════════════════════════ */
.stDataFrame {
    border: 1px solid var(--ivy-border) !important;
    border-radius: var(--ivy-radius) !important;
    overflow: hidden !important;
    box-shadow: var(--ivy-shadow) !important;
}

.stDataFrame table {
    font-family: var(--ivy-mono) !important;
    font-size: 0.82rem !important;
}

.stDataFrame thead th {
    background: var(--ivy-green) !important;
    color: white !important;
    font-family: var(--ivy-font) !important;
    font-weight: 600 !important;
    font-size: 0.8rem !important;
    letter-spacing: 0.03em !important;
    text-transform: uppercase !important;
    padding: 0.7rem 1rem !important;
    position: sticky !important;
    top: 0 !important;
    z-index: 2 !important;
}

.stDataFrame tbody tr:nth-child(even) {
    background: var(--ivy-accent) !important;
}

.stDataFrame tbody tr:hover {
    background: var(--ivy-green-light) !important;
}

.stDataFrame tbody td {
    padding: 0.55rem 1rem !important;
    border-bottom: 1px solid var(--ivy-border) !important;
    font-size: 0.85rem !important;
}

/* Sticky first column */
.stDataFrame tbody td:first-child,
.stDataFrame thead th:first-child {
    position: sticky !important;
    left: 0 !important;
    background: var(--ivy-white) !important;
    z-index: 1 !important;
    font-weight: 500 !important;
}

/* Mobile table scroll */
@media (max-width: 768px) {
    .stDataFrame {
        overflow-x: auto !important;
        -webkit-overflow-scrolling: touch !important;
    }
    .stDataFrame table {
        font-size: 0.75rem !important;
    }
    .stDataFrame tbody td,
    .stDataFrame thead th {
        padding: 0.45rem 0.6rem !important;
    }
}

/* ═══════════════════════════════════════════════
   METRICS
═══════════════════════════════════════════════ */
[data-testid="metric-container"] {
    background: var(--ivy-white) !important;
    border: 1px solid var(--ivy-border) !important;
    border-radius: var(--ivy-radius) !important;
    padding: 1rem 1.2rem !important;
    box-shadow: var(--ivy-shadow) !important;
}

[data-testid="metric-container"] [data-testid="stMetricLabel"] {
    font-size: 0.78rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.05em !important;
    text-transform: uppercase !important;
    color: var(--ivy-text-soft) !important;
}

[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-size: 1.6rem !important;
    font-weight: 700 !important;
    color: var(--ivy-green) !important;
    font-family: var(--ivy-mono) !important;
}

/* ═══════════════════════════════════════════════
   ALERTS / INFO BOXES
═══════════════════════════════════════════════ */
.stAlert {
    border-radius: var(--ivy-radius-sm) !important;
    border: none !important;
    font-size: 0.88rem !important;
}

/* Info */
[data-baseweb="notification"][kind="info"],
.stAlert[data-baseweb="notification"] {
    background: var(--ivy-green-light) !important;
    border-left: 3px solid var(--ivy-green) !important;
    color: var(--ivy-text) !important;
}

/* Success */
div[data-testid="stNotification"][kind="success"],
.element-container .stSuccess {
    background: #edf7f4 !important;
    border-left: 3px solid var(--ivy-success) !important;
}

/* Warning */
div[data-testid="stNotification"][kind="warning"],
.element-container .stWarning {
    background: #fef9ec !important;
    border-left: 3px solid var(--ivy-warning) !important;
}

/* Error */
div[data-testid="stNotification"][kind="error"],
.element-container .stError {
    background: #fdf0ef !important;
    border-left: 3px solid var(--ivy-danger) !important;
}

/* ═══════════════════════════════════════════════
   EXPANDERS
═══════════════════════════════════════════════ */
.streamlit-expanderHeader {
    background: var(--ivy-white) !important;
    border: 1px solid var(--ivy-border) !important;
    border-radius: var(--ivy-radius-sm) !important;
    font-weight: 500 !important;
    font-size: 0.9rem !important;
    color: var(--ivy-text) !important;
    padding: 0.7rem 1rem !important;
}

.streamlit-expanderHeader:hover {
    background: var(--ivy-green-light) !important;
    border-color: var(--ivy-green) !important;
}

.streamlit-expanderContent {
    border: 1px solid var(--ivy-border) !important;
    border-top: none !important;
    border-radius: 0 0 var(--ivy-radius-sm) var(--ivy-radius-sm) !important;
    padding: 1rem !important;
    background: var(--ivy-white) !important;
}

/* ═══════════════════════════════════════════════
   TABS
═══════════════════════════════════════════════ */
.stTabs [data-baseweb="tab-list"] {
    background: var(--ivy-white) !important;
    border-bottom: 2px solid var(--ivy-border) !important;
    gap: 0 !important;
}

.stTabs [data-baseweb="tab"] {
    font-family: var(--ivy-font) !important;
    font-size: 0.88rem !important;
    font-weight: 500 !important;
    color: var(--ivy-text-soft) !important;
    padding: 0.7rem 1.2rem !important;
    border-radius: var(--ivy-radius-sm) var(--ivy-radius-sm) 0 0 !important;
    transition: all 0.15s ease !important;
}

.stTabs [aria-selected="true"] {
    color: var(--ivy-green) !important;
    border-bottom: 2px solid var(--ivy-green) !important;
    font-weight: 600 !important;
    background: var(--ivy-green-light) !important;
}

/* ═══════════════════════════════════════════════
   DIVIDERS
═══════════════════════════════════════════════ */
hr {
    border: none !important;
    border-top: 1px solid var(--ivy-border) !important;
    margin: 1.5rem 0 !important;
}

/* ═══════════════════════════════════════════════
   CAPTION / SMALL TEXT
═══════════════════════════════════════════════ */
.stCaption, small, caption {
    font-size: 0.78rem !important;
    color: var(--ivy-text-muted) !important;
}

/* ═══════════════════════════════════════════════
   RADIO & CHECKBOX
═══════════════════════════════════════════════ */
.stRadio > div,
.stCheckbox > div {
    gap: 0.3rem !important;
}

.stRadio label,
.stCheckbox label {
    font-size: 0.9rem !important;
    color: var(--ivy-text) !important;
    cursor: pointer !important;
}

/* ═══════════════════════════════════════════════
   DATE INPUT
═══════════════════════════════════════════════ */
.stDateInput > div > div > input {
    border: 1.5px solid var(--ivy-border) !important;
    border-radius: var(--ivy-radius-sm) !important;
    font-family: var(--ivy-font) !important;
    font-size: 0.92rem !important;
}

/* ═══════════════════════════════════════════════
   LOGIN PAGE SPECIAL
═══════════════════════════════════════════════ */
.login-container {
    max-width: 420px;
    margin: 3rem auto;
    background: var(--ivy-white);
    border-radius: var(--ivy-radius);
    padding: 2.5rem;
    box-shadow: 0 4px 32px rgba(26,107,90,0.12);
    border: 1px solid var(--ivy-border);
}

/* ═══════════════════════════════════════════════
   SCROLLBAR
═══════════════════════════════════════════════ */
::-webkit-scrollbar {
    width: 6px;
    height: 6px;
}
::-webkit-scrollbar-track {
    background: var(--ivy-bg);
}
::-webkit-scrollbar-thumb {
    background: var(--ivy-border);
    border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
    background: var(--ivy-text-muted);
}

/* ═══════════════════════════════════════════════
   HIDE STREAMLIT BRANDING
═══════════════════════════════════════════════ */
#MainMenu { visibility: hidden !important; }
footer { visibility: hidden !important; }
[data-testid="stToolbar"] { display: none !important; }

/* ═══════════════════════════════════════════════
   MOBILE SIDEBAR TOGGLE — ALWAYS VISIBLE
═══════════════════════════════════════════════ */

/* The hamburger toggle button — always visible, green pill */
[data-testid="collapsedControl"] {
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    position: fixed !important;
    top: 0.6rem !important;
    left: 0.6rem !important;
    z-index: 999999 !important;
    background: var(--ivy-green) !important;
    border-radius: 8px !important;
    width: 2.8rem !important;
    height: 2.8rem !important;
    align-items: center !important;
    justify-content: center !important;
    box-shadow: 0 2px 12px rgba(26,107,90,0.3) !important;
    cursor: pointer !important;
}

[data-testid="collapsedControl"] svg {
    fill: white !important;
    color: white !important;
}

/* ═══════════════════════════════════════════════
   MOBILE — GENERAL TWEAKS
═══════════════════════════════════════════════ */
@media (max-width: 768px) {
    /* Padding so content doesn't hide behind toggle button */
    .main .block-container {
        padding-top: 3.5rem !important;
    }

    /* Stack columns on mobile */
    [data-testid="column"] {
        min-width: 100% !important;
    }

    /* Bigger tap targets */
    button, input, select, textarea {
        min-height: 44px !important;
    }
}
</style>
"""


def apply_styles():
    """Call this in app.py to apply all Ivy Pharmaceuticals styles."""
    import streamlit as st
    st.markdown(IVY_CSS, unsafe_allow_html=True)
