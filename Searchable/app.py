"""
app.py — ERP Student Lookup Backend
=====================================
Accepts a CRN from the frontend, builds the ERP URL
(base64-encoded CRN), fetches the student page, parses
it, and returns clean JSON.  Also proxies student photos
to avoid browser CORS restrictions.

Run:
    pip install -r requirements.txt
    python app.py

Then open:  http://localhost:5000
"""

import base64
import logging
import re
from io import BytesIO
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, render_template, request, send_file

# ── Logging ───────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────
ERP_BASE = "https://erp.tcioe.edu.np"
ERP_URL  = ERP_BASE + "/student/{program}/{encoded}/show?from=idcard"

CRN_PATTERN = re.compile(r"^THA(\d{3})([A-Z]{2,3})(\d{3})$")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# ── Flask app ─────────────────────────────────────────────────
app = Flask(__name__)

# Persistent HTTP session — reuses TCP connections for speed
erp_session = requests.Session()
erp_session.headers.update(HEADERS)


# ── Helpers ───────────────────────────────────────────────────

def encode_crn(crn: str) -> str:
    """Base64-encode the CRN exactly as the ERP expects."""
    return base64.b64encode(crn.encode()).decode()


def validate_crn(crn: str) -> tuple[bool, str]:
    """
    Returns (is_valid, error_message).
    Valid example: THA079BCT001
    """
    if not crn:
        return False, "CRN cannot be empty."
    if not CRN_PATTERN.match(crn):
        return False, (
            f'"{crn}" is not a valid CRN. '
            "Expected format: THA079BCT001 "
            "(campus prefix + 3-digit year + program code + 3-digit roll)."
        )
    return True, ""


def parse_student_page(html: str, crn: str, page_url: str) -> dict:
    """
    Parse the ERP student ID card HTML and return a structured dict.
    The ERP renders a <table> with label/value rows.
    """
    soup = BeautifulSoup(html, "html.parser")

    # No table → student record does not exist
    if not soup.find("table"):
        return {}

    data: dict = {}

    # ── Parse table rows ──────────────────────────────────────
    table = soup.find("table")
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        label = cells[0].get_text(strip=True)
        value = cells[1].get_text(strip=True)

        if "CRN"             in label:                              data["crn"]         = value
        elif "Name"          in label:                              data["name"]        = value
        elif "Program"       in label:                              data["program"]     = value
        elif "Date of Birth" in label:                              data["dob"]         = value
        elif "Address"       in label:                              data["address"]     = value
        elif "Contact"       in label and "Website" not in label:   data["contact"]     = value
        elif "Citizenship"   in label:                              data["citizenship"] = value

    # Guard: if the CRN field is empty the record is a blank placeholder
    if not data.get("crn"):
        return {}

    # ── Photo URL ─────────────────────────────────────────────
    img_tag = soup.find("img")
    if img_tag and img_tag.get("src"):
        img_src = img_tag["src"].replace("\\", "/")
        data["photo_url"] = urljoin(page_url, img_src)

    return data


# ── Routes ────────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the search frontend."""
    return render_template("search.html")


@app.route("/api/search", methods=["POST"])
def api_search():
    """
    POST /api/search
    Body (JSON): { "crn": "THA079BCT001" }
    Returns student data as JSON or an error object.
    """
    body = request.get_json(silent=True) or {}
    raw_crn = (body.get("crn") or "").strip().upper()

    # ── Validate ──────────────────────────────────────────────
    ok, err = validate_crn(raw_crn)
    if not ok:
        return jsonify({"error": err}), 400

    match = CRN_PATTERN.match(raw_crn)
    program = match.group(2)

    # ── Build ERP URL ─────────────────────────────────────────
    encoded  = encode_crn(raw_crn)
    page_url = ERP_URL.format(program=program, encoded=encoded)
    log.info("Fetching ERP → %s", page_url)

    # ── Fetch ─────────────────────────────────────────────────
    try:
        resp = erp_session.get(page_url, timeout=15)
        resp.raise_for_status()
    except requests.Timeout:
        log.error("ERP request timed out for %s", raw_crn)
        return jsonify({"error": "ERP request timed out. Try again."}), 504
    except requests.ConnectionError:
        log.error("Cannot reach ERP for %s", raw_crn)
        return jsonify({"error": "Cannot connect to ERP. Check your internet connection."}), 503
    except requests.HTTPError as exc:
        log.error("ERP HTTP error for %s: %s", raw_crn, exc)
        return jsonify({"error": f"ERP returned an error: {exc}"}), 502

    # ── Parse ─────────────────────────────────────────────────
    data = parse_student_page(resp.text, raw_crn, page_url)

    if not data:
        log.info("No record found for %s", raw_crn)
        return jsonify({"error": f'No student record found for CRN "{raw_crn}".'}), 404

    log.info("Found: %s — %s", data.get("crn"), data.get("name"))
    return jsonify(data), 200


@app.route("/api/photo")
def api_photo():
    """
    GET /api/photo?url=<ERP_photo_url>
    Proxies the student photo from the ERP to avoid browser
    CORS/mixed-content restrictions.  Only allows URLs that
    originate from the ERP domain.
    """
    photo_url = request.args.get("url", "").strip()

    if not photo_url:
        return "", 404

    # Security: only proxy images from the ERP domain
    if not photo_url.startswith(ERP_BASE):
        log.warning("Blocked proxy attempt for non-ERP URL: %s", photo_url)
        return "Forbidden", 403

    try:
        resp = erp_session.get(photo_url, timeout=10)
        resp.raise_for_status()
        mime = resp.headers.get("Content-Type", "image/jpeg").split(";")[0]
        return send_file(BytesIO(resp.content), mimetype=mime)
    except requests.RequestException as exc:
        log.warning("Photo proxy failed for %s: %s", photo_url, exc)
        return "", 404


# ── Entry point ───────────────────────────────────────────────

if __name__ == "__main__":
    log.info("Starting ERP Lookup server at http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
