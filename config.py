# ═══════════════════════════════════════════════════════════
#  config.py  —  ERP connection settings
#  Fill in every value marked  ← CONFIGURE  before running.
# ═══════════════════════════════════════════════════════════

# ── ERP Base URL ─────────────────────────────────────────────
# The root URL of the campus ERP, no trailing slash.
# Example: "https://erp.tcioe.edu.np"
ERP_BASE_URL = "https://your-erp-url.edu.np"          # ← CONFIGURE

# ── Endpoints (relative to ERP_BASE_URL) ─────────────────────
# Open the ERP in your browser, log in manually, then copy the
# exact URL paths from the address bar for each action below.
LOGIN_ENDPOINT  = "/login"                             # ← CONFIGURE
SEARCH_ENDPOINT = "/student/search"                    # ← CONFIGURE

# ── Admin credentials ─────────────────────────────────────────
ERP_USERNAME = "admin"                                 # ← CONFIGURE
ERP_PASSWORD = "password"                              # ← CONFIGURE

# ── HTTP settings ─────────────────────────────────────────────
REQUEST_TIMEOUT = 15   # seconds before giving up on ERP

# ── Flask server settings ─────────────────────────────────────
FLASK_PORT  = 5000
FLASK_DEBUG = False    # set True only while developing locally
