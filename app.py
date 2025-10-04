import os, json, datetime
import requests
from flask import Flask, request, render_template, jsonify, abort, redirect
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from db import init_db, db, now_iso, fetch_offer_snapshot
from admin_views import bp as admin_bp

# ---------- Config ----------
SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
BASE_URL = os.getenv("BASE_URL", "http://localhost:5000")
TOKEN_MAX_AGE_SECONDS = int(os.getenv("TOKEN_MAX_AGE_SECONDS", str(7*24*3600)))

ORDER_API_URL = os.getenv(
    "ORDER_API_URL",
    "http://10.8.219.66:8501/rest/oapi/order/create_new"  # your test host
)
ORDER_API_TIMEOUT = 10

app = Flask(__name__)
app.config.update(SECRET_KEY=SECRET_KEY, BASE_URL=BASE_URL)
signer = URLSafeTimedSerializer(SECRET_KEY)
app.config["SIGNER"] = signer

# DB init
init_db()

# ---------- Jinja filters ----------
@app.template_filter("fmt_dt")
def fmt_dt(iso):
    if not iso: return ""
    try:
        return iso.replace("T"," ").replace("+00:00","Z")
    except:
        return iso

# ---------- Admin ----------
app.register_blueprint(admin_bp)

# ---------- Public Landing (Agree/Reject) ----------
@app.get("/l/<token>")
def landing(token):
    try:
        data = signer.loads(token, max_age=TOKEN_MAX_AGE_SECONDS)
    except SignatureExpired:
        return "Link expired.", 410
    except BadSignature:
        return "Invalid link.", 400

    with db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM links WHERE id=?", (data["lid"],))
        link = c.fetchone()
        if not link: return "Not found.", 404

        # Expired?
        if link["expires_at"]:
            exp = datetime.datetime.fromisoformat(link["expires_at"])
            if exp < datetime.datetime.now(datetime.timezone.utc):
                c.execute("UPDATE links SET status='EXPIRED' WHERE id=?", (link["id"],))
                conn.commit()
                return "Link expired.", 410

        # Mark opened once
        if not link["opened_at"]:
            c.execute("UPDATE links SET opened_at=?, status='OPENED' WHERE id=?", (now_iso(), link["id"]))
            conn.commit()

        offer = json.loads(link["offer_snapshot_json"])
        return render_template("landing.html", offer=offer, token=token, link_id=link["id"])

@app.post("/api/agree")
def api_agree():
    token = request.form.get("token") or (request.json or {}).get("token")
    if not token: abort(400, "Missing token")
    try:
        data = signer.loads(token, max_age=TOKEN_MAX_AGE_SECONDS)
    except SignatureExpired:
        return jsonify({"status":"expired"}), 410
    except BadSignature:
        return jsonify({"status":"invalid"}), 400

    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    ua = request.headers.get("User-Agent", "")
    now = now_iso()

    with db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM links WHERE id=?", (data["lid"],))
        link = c.fetchone()
        if not link: return jsonify({"status":"not_found"}), 404
        if link["status"] == "AGREED":
            return jsonify({"status":"already_agreed"}), 200

        offer = json.loads(link["offer_snapshot_json"])
        consent_text = f"Agreed to '{offer['title']}' ({offer['bundle']}) at {now}"
        c.execute("""INSERT INTO consents (link_id, consent_text, choice, created_at, ip, user_agent)
                     VALUES (?, ?, 'AGREED', ?, ?, ?)""",
                  (link["id"], consent_text, now, ip, ua))
        c.execute("UPDATE links SET agreed_at=?, status='AGREED' WHERE id=?", (now, link["id"]))
        conn.commit()

    # Optional: create order
    try:
        create_order_from_offer(link_id=link["id"])
    except Exception as e:
        print("Order API error:", e)

    return jsonify({"status":"ok", "message":"Consent recorded", "agreed_at": now})

@app.post("/api/reject")
def api_reject():
    token = request.form.get("token") or (request.json or {}).get("token")
    if not token: abort(400, "Missing token")
    try:
        data = signer.loads(token, max_age=TOKEN_MAX_AGE_SECONDS)
    except SignatureExpired:
        return jsonify({"status":"expired"}), 410
    except BadSignature:
        return jsonify({"status":"invalid"}), 400

    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    ua = request.headers.get("User-Agent", "")
    now = now_iso()

    with db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM links WHERE id=?", (data["lid"],))
        link = c.fetchone()
        if not link: return jsonify({"status":"not_found"}), 404
        if link["status"] in ("AGREED","REJECTED"):
            return jsonify({"status":"already_final"}), 200

        offer = json.loads(link["offer_snapshot_json"])
        consent_text = f"Rejected '{offer['title']}' ({offer['bundle']}) at {now}"
        c.execute("""INSERT INTO consents (link_id, consent_text, choice, created_at, ip, user_agent)
                     VALUES (?, ?, 'REJECTED', ?, ?, ?)""",
                  (link["id"], consent_text, now, ip, ua))
        c.execute("UPDATE links SET rejected_at=?, status='REJECTED' WHERE id=?", (now, link["id"]))
        conn.commit()

    return jsonify({"status":"ok", "message":"Rejection recorded", "rejected_at": now})

from flask import render_template  # (already imported above in your app)

# --------- Page: Agree (renders HTML) ----------
@app.post("/agree")
def agree_page():
    token = request.form.get("token") or (request.json or {}).get("token")
    if not token: return render_template("decision_error.html", title="Ошибка", message="Отсутствует токен."), 400

    try:
        data = signer.loads(token, max_age=TOKEN_MAX_AGE_SECONDS)
    except SignatureExpired:
        return render_template("decision_error.html", title="Ссылка истекла", message="Срок действия ссылки закончился."), 410
    except BadSignature:
        return render_template("decision_error.html", title="Неверная ссылка", message="Недействительный токен."), 400

    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    ua = request.headers.get("User-Agent", "")
    now = now_iso()

    with db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM links WHERE id=?", (data["lid"],))
        link = c.fetchone()
        if not link:
            return render_template("decision_error.html", title="Не найдено", message="Ссылка не найдена."), 404

        # expired?
        if link["expires_at"]:
            exp = datetime.datetime.fromisoformat(link["expires_at"])
            if exp < datetime.datetime.now(datetime.timezone.utc):
                c.execute("UPDATE links SET status='EXPIRED' WHERE id=?", (link["id"],))
                conn.commit()
                return render_template("decision_error.html", title="Ссылка истекла", message="Срок действия ссылки закончился."), 410

        offer = json.loads(link["offer_snapshot_json"])

        # already final?
        if link["status"] == "REJECTED":
            return render_template("rejected.html", offer=offer, when=link["rejected_at"], already=True)
        if link["status"] == "AGREED":
            return render_template("accepted.html", offer=offer, when=link["agreed_at"], already=True)

        # mark opened if first time
        if not link["opened_at"]:
            c.execute("UPDATE links SET opened_at=? WHERE id=?", (now, link["id"]))

        # store consent & update status
        consent_text = f"Agreed to '{offer['title']}' ({offer.get('bundle')}) at {now}"
        c.execute("""INSERT INTO consents (link_id, consent_text, choice, created_at, ip, user_agent)
                     VALUES (?, ?, 'AGREED', ?, ?, ?)""",
                  (link["id"], consent_text, now, ip, ua))
        c.execute("UPDATE links SET agreed_at=?, status='AGREED' WHERE id=?", (now, link["id"]))
        conn.commit()

    # Optional: create order (same as /api/agree)
    try:
        create_order_from_offer(link_id=link["id"])
    except Exception as e:
        print("Order API error:", e)

    return render_template("accepted.html", offer=offer, when=now, already=False)


# --------- Page: Reject (renders HTML) ----------
@app.post("/reject")
def reject_page():
    token = request.form.get("token") or (request.json or {}).get("token")
    if not token: return render_template("decision_error.html", title="Ошибка", message="Отсутствует токен."), 400

    try:
        data = signer.loads(token, max_age=TOKEN_MAX_AGE_SECONDS)
    except SignatureExpired:
        return render_template("decision_error.html", title="Ссылка истекла", message="Срок действия ссылки закончился."), 410
    except BadSignature:
        return render_template("decision_error.html", title="Неверная ссылка", message="Недействительный токен."), 400

    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    ua = request.headers.get("User-Agent", "")
    now = now_iso()

    with db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM links WHERE id=?", (data["lid"],))
        link = c.fetchone()
        if not link:
            return render_template("decision_error.html", title="Не найдено", message="Ссылка не найдена."), 404

        # expired?
        if link["expires_at"]:
            exp = datetime.datetime.fromisoformat(link["expires_at"])
            if exp < datetime.datetime.now(datetime.timezone.utc):
                c.execute("UPDATE links SET status='EXPIRED' WHERE id=?", (link["id"],))
                conn.commit()
                return render_template("decision_error.html", title="Ссылка истекла", message="Срок действия ссылки закончился."), 410

        offer = json.loads(link["offer_snapshot_json"])

        # already final?
        if link["status"] == "AGREED":
            return render_template("accepted.html", offer=offer, when=link["agreed_at"], already=True)
        if link["status"] == "REJECTED":
            return render_template("rejected.html", offer=offer, when=link["rejected_at"], already=True)

        # mark opened if first time
        if not link["opened_at"]:
            c.execute("UPDATE links SET opened_at=? WHERE id=?", (now, link["id"]))

        # store decision & update status
        consent_text = f"Rejected '{offer['title']}' ({offer.get('bundle')}) at {now}"
        c.execute("""INSERT INTO consents (link_id, consent_text, choice, created_at, ip, user_agent)
                     VALUES (?, ?, 'REJECTED', ?, ?, ?)""",
                  (link["id"], consent_text, now, ip, ua))
        c.execute("UPDATE links SET rejected_at=?, status='REJECTED' WHERE id=?", (now, link["id"]))
        conn.commit()

    return render_template("rejected.html", offer=offer, when=now, already=False)


# ---------- Internal: Order mapping ----------
def create_order_from_offer(link_id: int):
    with db() as conn:
        c = conn.cursor()
        c.execute("""SELECT l.*, u.filial_id, u.customer_account_id, u.id AS uid,
                            o.product_offer_id, o.product_offer_struct_id, o.po_struct_element_id,
                            o.product_num, o.resource_spec_id
                     FROM links l
                       JOIN users u ON u.id=l.user_id
                       JOIN offers o ON o.id=l.offer_id
                     WHERE l.id=?""", (link_id,))
        row = c.fetchone()
        if not row: return

        payload = {
            "FILIAL_ID": row["filial_id"] or 17,
            "CUSTOMER_ACCOUNT_ID": row["customer_account_id"],
            "SALES_CHANNEL_ID": 1,
            "EXTERNAL_ID": row["external_id"] or f"LNK-{link_id}",
            "PRODUCT_OFFER_ID": row["product_offer_id"],
            "ADDRESS": {"STREET_ID": 123, "HOUSE": 1, "ZIP_CODE": "050000"},
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
        print("Posting Order:", ORDER_API_URL)
        r = requests.post(ORDER_API_URL, json=payload, timeout=ORDER_API_TIMEOUT)
        print("Order response:", r.status_code, r.text)
        r.raise_for_status()


# ---------- Health ----------
# in app.py (or wherever you create app = Flask(__name__))
@app.get("/healthz")
def healthz():
    return {"status": "ok"}, 200

if __name__ == "__main__":
    app.run(debug=True)
