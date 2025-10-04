import os, sqlite3, json, datetime
from flask import Flask, request, redirect, render_template_string, jsonify, abort
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
import requests

# ---------- Config ----------
SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
BASE_URL = os.getenv("BASE_URL", "http://localhost:5000")   # public host for links
TOKEN_MAX_AGE_SECONDS = 60 * 60 * 24 * 7  # 7 days
DB_PATH = "app.db"

# (Optional) Internal Order API integration
ORDER_API_URL = "http://10.8.219.66:8501/rest/oapi/order/create_new"

ORDER_API_TIMEOUT = 10  # seconds

app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY
signer = URLSafeTimedSerializer(SECRET_KEY)


# ---------- DB helpers ----------
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as conn:
        c = conn.cursor()
        c.execute("""
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY,
          name TEXT,
          phone TEXT,
          email TEXT,
          filial_id INTEGER,
          customer_account_id INTEGER
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS offers (
          id INTEGER PRIMARY KEY,
          title TEXT,
          bundle TEXT,                  -- 'internet' | 'fms' | 'tv' | 'bundle'
          price NUMERIC,
          currency TEXT,
          details_json TEXT,            -- free-form details to render
          -- fields below help map to your Order API
          product_offer_id INTEGER,
          product_offer_struct_id INTEGER,
          po_struct_element_id INTEGER,
          product_num TEXT,
          resource_spec_id INTEGER
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS links (
          id INTEGER PRIMARY KEY,
          user_id INTEGER,
          offer_id INTEGER,
          external_id TEXT,             -- your tracking id
          token TEXT UNIQUE,
          expires_at TEXT,
          opened_at TEXT,
          agreed_at TEXT,
          status TEXT DEFAULT 'NEW',    -- NEW | OPENED | AGREED | EXPIRED | USED
          offer_snapshot_json TEXT,     -- store what was shown at the time of link creation
          FOREIGN KEY(user_id) REFERENCES users(id),
          FOREIGN KEY(offer_id) REFERENCES offers(id)
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS consents (
          id INTEGER PRIMARY KEY,
          link_id INTEGER,
          consent_text TEXT,
          created_at TEXT,
          ip TEXT,
          user_agent TEXT,
          FOREIGN KEY(link_id) REFERENCES links(id)
        )""")
        conn.commit()

init_db()


# ---------- Utilities ----------
def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def create_token(link_id: int) -> str:
    return signer.dumps({"lid": link_id})

def load_token(token: str):
    return signer.loads(token, max_age=TOKEN_MAX_AGE_SECONDS)

def link_url(token: str) -> str:
    return f"{BASE_URL}/l/{token}"

def fetch_offer_snapshot(cur, offer_id: int):
    cur.execute("SELECT * FROM offers WHERE id=?", (offer_id,))
    o = cur.fetchone()
    if not o: return None
    snapshot = dict(o)
    return {
        "id": snapshot["id"],
        "title": snapshot["title"],
        "bundle": snapshot["bundle"],
        "price": snapshot["price"],
        "currency": snapshot["currency"],
        "details": json.loads(snapshot["details_json"] or "{}"),
        "order_mapping": {
            "product_offer_id": snapshot["product_offer_id"],
            "product_offer_struct_id": snapshot["product_offer_struct_id"],
            "po_struct_element_id": snapshot["po_struct_element_id"],
            "product_num": snapshot["product_num"],
            "resource_spec_id": snapshot["resource_spec_id"],
        }
    }

def mark_opened(cur, link_row):
    if not link_row["opened_at"]:
        cur.execute("UPDATE links SET opened_at=?, status='OPENED' WHERE id=?",
                    (now_iso(), link_row["id"]))

# ---------- Admin: seed / create users & offers ----------
@app.post("/admin/user")
def admin_create_user():
    data = request.get_json(force=True)
    with db() as conn:
        c = conn.cursor()
        c.execute("""INSERT INTO users (name, phone, email, filial_id, customer_account_id)
                     VALUES (?, ?, ?, ?, ?)""",
                  (data.get("name"), data.get("phone"), data.get("email"),
                   data["filial_id"], data["customer_account_id"]))
        uid = c.lastrowid
        conn.commit()
    return {"user_id": uid}

@app.post("/admin/offer")
def admin_create_offer():
    data = request.get_json(force=True)
    with db() as conn:
        c = conn.cursor()
        c.execute("""INSERT INTO offers
            (title, bundle, price, currency, details_json,
             product_offer_id, product_offer_struct_id, po_struct_element_id, product_num, resource_spec_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["title"], data["bundle"], data.get("price"), data.get("currency","KZT"),
             json.dumps(data.get("details", {})),
             data.get("product_offer_id"), data.get("product_offer_struct_id"),
             data.get("po_struct_element_id"), data.get("product_num"), data.get("resource_spec_id")))
        oid = c.lastrowid
        conn.commit()
    return {"offer_id": oid}

@app.post("/admin/link")
def admin_create_link():
    """
    Body:
    {
      "user_id": 1,
      "offer_id": 2,
      "external_id": "SMS-2025-0001",
      "expires_days": 7
    }
    """
    data = request.get_json(force=True)
    expires_days = int(data.get("expires_days", 7))
    expires_at = (datetime.datetime.now(datetime.timezone.utc)
                  + datetime.timedelta(days=expires_days)).isoformat()

    with db() as conn:
        c = conn.cursor()
        snap = fetch_offer_snapshot(c, data["offer_id"])
        if not snap: abort(400, "Offer not found")

        c.execute("""INSERT INTO links (user_id, offer_id, external_id, expires_at, offer_snapshot_json)
                     VALUES (?, ?, ?, ?, ?)""",
                  (data["user_id"], data["offer_id"], data.get("external_id"),
                   expires_at, json.dumps(snap)))
        link_id = c.lastrowid
        token = create_token(link_id)
        c.execute("UPDATE links SET token=? WHERE id=?", (token, link_id))
        conn.commit()

    return {"link_id": link_id, "url": link_url(token), "expires_at": expires_at}

@app.post("/admin/links/bulk")
def admin_create_links_bulk():
    """
    Body: {"items": [{"user_id": 1, "offer_id": 2, "external_id": "SMS-1"}, ...]}
    """
    data = request.get_json(force=True)
    out = []
    with db() as conn:
        c = conn.cursor()
        for item in data.get("items", []):
            snap = fetch_offer_snapshot(c, item["offer_id"])
            if not snap: continue
            expires_at = (datetime.datetime.now(datetime.timezone.utc)
                          + datetime.timedelta(days=7)).isoformat()
            c.execute("""INSERT INTO links (user_id, offer_id, external_id, expires_at, offer_snapshot_json)
                         VALUES (?, ?, ?, ?, ?)""",
                      (item["user_id"], item["offer_id"], item.get("external_id"),
                       expires_at, json.dumps(snap)))
            link_id = c.lastrowid
            token = create_token(link_id)
            c.execute("UPDATE links SET token=? WHERE id=?", (token, link_id))
            out.append({"link_id": link_id, "url": link_url(token)})
        conn.commit()
    return {"links": out}


# ---------- Public: landing + agree ----------
LANDING_HTML = """
<!doctype html>
<html lang="en">
  <head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ offer.title }}</title>
    <style>
      body {font-family: system-ui, sans-serif; margin: 24px;}
      .card {max-width: 680px; padding: 24px; border: 1px solid #ddd; border-radius: 12px;}
      .cta {padding: 12px 16px; border: 0; border-radius: 10px; cursor: pointer;}
    </style>
  </head>
  <body>
    <div class="card">
      <h1>{{ offer.title }}</h1>
      <p><strong>Bundle:</strong> {{ offer.bundle|capitalize }}</p>
      {% if offer.price %}<p><strong>Price:</strong> {{ offer.price }} {{ offer.currency }}</p>{% endif %}
      {% if offer.details.speed %}<p><strong>Internet speed:</strong> {{ offer.details.speed }}</p>{% endif %}
      {% if offer.details.tv_channels %}<p><strong>TV channels:</strong> {{ offer.details.tv_channels }}</p>{% endif %}
      {% if offer.details.fms_desc %}<p><strong>FMS:</strong> {{ offer.details.fms_desc }}</p>{% endif %}

      <h3>Terms</h3>
      <ul>
        <li>By pressing Agree, you consent to connect the above subscription and accept pricing & terms.</li>
        <li>Consent time and your IP will be recorded. Token is single-use and may expire.</li>
      </ul>

      <form id="agreeForm" method="post" action="/api/agree">
        <input type="hidden" name="token" value="{{ token }}">
        <button class="cta" type="submit">Agree</button>
      </form>
    </div>
  </body>
</html>
"""

@app.get("/l/<token>")
def landing(token):
    try:
        data = load_token(token)
    except SignatureExpired:
        return "Link expired.", 410
    except BadSignature:
        return "Invalid link.", 400

    with db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM links WHERE id=?", (data["lid"],))
        link = c.fetchone()
        if not link: return "Not found", 404

        # Expiry and status checks
        if link["status"] in ("AGREED", "USED"):
            return "This link has already been used.", 409
        if link["expires_at"] and datetime.datetime.fromisoformat(link["expires_at"]) < datetime.datetime.now(datetime.timezone.utc):
            c.execute("UPDATE links SET status='EXPIRED' WHERE id=?", (link["id"],))
            conn.commit()
            return "Link expired.", 410

        mark_opened(c, link); conn.commit()

        offer = json.loads(link["offer_snapshot_json"])
        return render_template_string(LANDING_HTML, offer=offer, token=token)

@app.post("/api/agree")
def api_agree():
    token = request.form.get("token") or (request.json or {}).get("token")
    if not token: abort(400, "Missing token")

    try:
        data = load_token(token)
    except SignatureExpired:
        return jsonify({"status": "expired"}), 410
    except BadSignature:
        return jsonify({"status": "invalid"}), 400

    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    ua = request.headers.get("User-Agent", "")
    now = now_iso()

    with db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM links WHERE id=?", (data["lid"],))
        link = c.fetchone()
        if not link: return jsonify({"status": "not_found"}), 404
        if link["status"] == "AGREED":
            return jsonify({"status": "already_agreed"}), 200

        offer = json.loads(link["offer_snapshot_json"])

        # 1) store consent
        consent_text = f"Agreed to '{offer['title']}' ({offer['bundle']}) at {now}"
        c.execute("""INSERT INTO consents (link_id, consent_text, created_at, ip, user_agent)
                     VALUES (?, ?, ?, ?, ?)""",
                  (link["id"], consent_text, now, ip, ua))

        # 2) mark link used
        c.execute("UPDATE links SET agreed_at=?, status='AGREED' WHERE id=?", (now, link["id"]))
        conn.commit()

    # 3) (optional) create order in your internal system
    try:
        create_order_from_offer(link_id=link["id"])
    except Exception as e:
        # Don’t block the customer—just log. You can retry out of band if needed.
        print("Order API error:", e)

    return jsonify({"status": "ok", "message": "Consent recorded", "agreed_at": now})

def create_order_from_offer(link_id: int):
    """Map the stored offer snapshot -> your internal order API payload."""
    with db() as conn:
        c = conn.cursor()
        c.execute("""SELECT links.*, users.*, offers.* FROM links
                     JOIN users ON users.id = links.user_id
                     JOIN offers ON offers.id = links.offer_id
                     WHERE links.id=?""", (link_id,))
        row = c.fetchone()
        if not row: return

        # Minimal mapping. Adjust to your exact API schema.
        payload = {
            "FILIAL_ID": row["filial_id"],
            "CUSTOMER_ACCOUNT_ID": row["customer_account_id"],
            "SALES_CHANNEL_ID": 1,
            "EXTERNAL_ID": row["external_id"] or f"LNK-{link_id}",
            "PRODUCT_OFFER_ID": row["product_offer_id"],
            "ADDRESS": {
                # Replace with real address fields if you have them; placeholders here:
                "STREET_ID": 123, "HOUSE": 1, "ZIP_CODE": "050000"
            },
            "CUST_ORDER_ITEMS": [{
                "EXTERNAL_ID": f"{row['external_id'] or f'LNK-{link_id}'}-1",
                "ORDER_NUM": 1,
                "PO_COMPONENT_ID": -1,
                "PRODUCT_OFFER_STRUCT_ID": row["product_offer_struct_id"],
                "PRODUCT_NUM": row["product_num"],
                "RESOURCE_SPEC_ID": row["resource_spec_id"],
                "SERVICE_COUNT": 1,
                "PO_STRUCT_ELEMENTS": [{
                    "PO_STRUCT_ELEMENT_ID": row["po_struct_element_id"],
                    "ACTION_DATE": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.000"),
                    "SERVICE_COUNT": 1
                }]
            }]
        }
        r = requests.post(ORDER_API_URL, json=payload, timeout=ORDER_API_TIMEOUT)
        if r.status_code >= 300:
            raise RuntimeError(f"Order API {r.status_code}: {r.text}")


@app.get("/admin/consents")
def admin_list_consents():
    limit = int(request.args.get("limit", 20))
    with db() as conn:
        c = conn.cursor()
        c.execute("""SELECT consents.id, link_id, consent_text, created_at, ip
                     FROM consents ORDER BY id DESC LIMIT ?""", (limit,))
        rows = [dict(r) for r in c.fetchall()]
    return {"consents": rows}

@app.get("/admin/link/<int:link_id>")
def admin_get_link(link_id):
    with db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM links WHERE id=?", (link_id,))
        row = c.fetchone()
        if not row: return {"error": "not_found"}, 404
    return {"link": dict(row)}

@app.post("/admin/retry_order")
def admin_retry_order():
    data = request.get_json(force=True)
    link_id = int(data["link_id"])
    create_order_from_offer(link_id)
    return {"status": "sent"}

if __name__ == "__main__":
    app.run(debug=True)
