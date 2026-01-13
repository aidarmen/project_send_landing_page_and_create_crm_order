import os, json, datetime
import sys
import logging, uuid
from dotenv import load_dotenv
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from flask import Flask, request, render_template, jsonify, abort, redirect
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from db import init_db, db, now_iso, fetch_offer_snapshot
from admin_views import bp as admin_bp
try:
    from version import get_version
    PROJECT_VERSION = get_version()
except ImportError:
    PROJECT_VERSION = "unknown"
from translations import get_all_translations

# ---------- Config ----------
load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
    # BASE_URL: use environment variable, but if empty or not set, use localhost default
    _base_url = os.getenv("BASE_URL", "").strip()
    BASE_URL = _base_url if _base_url else "http://localhost:5000"
    TOKEN_MAX_AGE_SECONDS = int(os.getenv("TOKEN_MAX_AGE_SECONDS", str(7 * 24 * 3600)))
    ORDER_API_URL = os.getenv("ORDER_API_URL", "")
    ORDER_API_KEY = os.getenv("ORDER_API_KEY", "")
    ORDER_API_TIMEOUT = int(os.getenv("ORDER_API_TIMEOUT", "10"))
    DB_PATH = os.getenv("DB_PATH")  # used by db.py if provided


def validate_config():
    """Validate required configuration fields"""
    errors = []
    if not app.config.get("ORDER_API_KEY"):
        errors.append("ORDER_API_KEY is required")
    if not app.config.get("ORDER_API_URL"):
        errors.append("ORDER_API_URL is required")
    if app.config.get("SECRET_KEY") == "change-me":
        print("WARNING: SECRET_KEY is set to default value 'change-me'")
    base_url = app.config.get("BASE_URL", "")
    if not base_url or base_url == "http://localhost:5000":
        print("WARNING: BASE_URL is set to default 'http://localhost:5000'")
        print("  This will cause generated links to use localhost instead of your production domain.")
        print("  Please set BASE_URL environment variable in your .env file or Docker environment.")
    if errors:
        print("ERROR: Missing required configuration:")
        for err in errors:
            print(f"  - {err}")
        print("\nPlease set the required environment variables in your .env file.")
        print("See env.example for reference.")
        sys.exit(1)


app = Flask(__name__)
app.config.from_object(Config)
signer = URLSafeTimedSerializer(app.config["SECRET_KEY"])
app.config["SIGNER"] = signer

# ---------- Logging & Request ID ----------
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

# Log BASE_URL for debugging
logging.info(f"BASE_URL configured as: {app.config.get('BASE_URL')}")

# Validate configuration before initializing database
validate_config()

# DB init
init_db()

# Log version on startup
logging.info(f"Starting application version: {PROJECT_VERSION}")

# Make version available to all templates
@app.context_processor
def inject_version():
    return dict(version=PROJECT_VERSION)

from flask import g

@app.before_request
def assign_request_id():
    rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    g.request_id = rid

@app.after_request
def add_request_id_hdr(resp):
    rid = getattr(g, 'request_id', None)
    if rid:
        resp.headers['X-Request-ID'] = rid
    return resp

# ---------- Jinja filters ----------
@app.template_filter("fmt_dt")
def fmt_dt(iso):
    if not iso: return ""
    try:
        return iso.replace("T"," ").replace("+00:00","Z")
    except:
        return iso

@app.template_filter("force_https")
def force_https(url):
    """Force HTTPS in URLs (except for localhost)"""
    if not url:
        return url
    url_str = str(url)
    # Force HTTPS unless it's localhost
    if url_str.startswith("http://") and not url_str.startswith("http://localhost") and not url_str.startswith("http://127.0.0.1"):
        return url_str.replace("http://", "https://", 1)
    return url_str

# ---------- Admin ----------
app.register_blueprint(admin_bp)

# ---------- Version API ----------
@app.get("/api/version")
def api_version():
    """API endpoint to get current application version"""
    return jsonify({
        "version": PROJECT_VERSION,
        "status": "ok"
    })

# ---------- Root redirect ----------
@app.get("/")
def root_redirect():
    """Redirect root path from b2c2.telecom.kz to telecom.kz"""
    # Only redirect exact root path "/" (not /admin/ or /l/<token>)
    # Flask will handle /admin/ and /l/<token> before this route
    path = request.path
    if path != "/":
        return "Not found", 404
    
    # Only redirect if accessed via b2c2.telecom.kz
    host = request.host
    if host and "b2c2.telecom.kz" in host:
        return redirect("https://telecom.kz", code=301)
    # Otherwise, return a simple response
    return "Not found", 404

# ---------- Public Landing (Agree/Reject) ----------
@app.get("/l/<token>")
def landing(token):
    try:
        data = signer.loads(token, max_age=app.config["TOKEN_MAX_AGE_SECONDS"])
    except SignatureExpired:
        return "Link expired.", 410
    except BadSignature:
        return "Invalid link.", 400

    # Language detection: URL parameter > cookie > default (ru)
    lang = request.args.get("lang", "").lower()
    if lang not in ("ru", "kk"):
        lang = request.cookies.get("landing_lang", "ru")
        if lang not in ("ru", "kk"):
            lang = "ru"
    
    # Flag to set cookie if language was changed via URL parameter
    set_lang_cookie = request.args.get("lang") and request.args.get("lang").lower() in ("ru", "kk")

    with db() as conn:
        c = conn.cursor()
        # Fetch link with user data
        c.execute("""SELECT l.*, u.customer_account_id 
                     FROM links l 
                     JOIN users u ON u.id = l.user_id 
                     WHERE l.id=?""", (data["lid"],))
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
        
        # Apply translations to offer if available
        if offer.get("details") and offer["details"].get("translations"):
            translations_data = offer["details"]["translations"]
            
            # For Kazakh language, use Russian as fallback
            if lang == "kk":
                # Get Russian translations as fallback
                ru_translations = translations_data.get("ru", {})
                kk_translations = translations_data.get("kk", {})
                
                # Override title: use Kazakh if available, otherwise Russian, otherwise keep original
                if "title" in kk_translations:
                    offer["title"] = kk_translations["title"]
                elif "title" in ru_translations:
                    offer["title"] = ru_translations["title"]
                
                # Override badges: use Kazakh if available, otherwise Russian
                if "badges" in kk_translations:
                    offer["details"]["badges"] = kk_translations["badges"]
                elif "badges" in ru_translations:
                    offer["details"]["badges"] = ru_translations["badges"]
                
                # Override component titles: use Kazakh if available, otherwise Russian
                if offer["details"].get("components"):
                    kk_components = kk_translations.get("components", [])
                    ru_components = ru_translations.get("components", [])
                    
                    # Create lookup dictionaries for faster access
                    kk_comp_map = {c.get("type"): c for c in kk_components if c.get("type")}
                    ru_comp_map = {c.get("type"): c for c in ru_components if c.get("type")}
                    
                    for comp in offer["details"]["components"]:
                        comp_type = comp.get("type")
                        if comp_type:
                            # Try Kazakh first, then Russian
                            if comp_type in kk_comp_map and "title" in kk_comp_map[comp_type]:
                                comp["title"] = kk_comp_map[comp_type]["title"]
                            elif comp_type in ru_comp_map and "title" in ru_comp_map[comp_type]:
                                comp["title"] = ru_comp_map[comp_type]["title"]
            elif lang == "ru" and "ru" in translations_data:
                # For Russian, use Russian translations directly
                ru_translations = translations_data["ru"]
                if "title" in ru_translations:
                    offer["title"] = ru_translations["title"]
                if "badges" in ru_translations:
                    offer["details"]["badges"] = ru_translations["badges"]
                if "components" in ru_translations and offer["details"].get("components"):
                    ru_components = ru_translations["components"]
                    ru_comp_map = {c.get("type"): c for c in ru_components if c.get("type")}
                    for comp in offer["details"]["components"]:
                        comp_type = comp.get("type")
                        if comp_type and comp_type in ru_comp_map and "title" in ru_comp_map[comp_type]:
                            comp["title"] = ru_comp_map[comp_type]["title"]
        
        # Parse address from link
        address = None
        if link["address_json"]:
            try:
                address = json.loads(link["address_json"])
            except (json.JSONDecodeError, TypeError):
                pass
        
        # Get all translations for current language
        translations = get_all_translations(lang)
        
        template_response = render_template("landing.html", 
                             offer=offer, 
                             token=token, 
                             link_id=link["id"],
                             customer_account_id=link["customer_account_id"],
                             address=address,
                             current_lang=lang,
                             translations=translations)
        
        # Set cookie if language was changed via URL parameter
        if set_lang_cookie:
            from flask import make_response
            response = make_response(template_response)
            response.set_cookie("landing_lang", lang, max_age=31536000)  # 1 year
            return response
        
        return template_response

@app.post("/api/agree")
def api_agree():
    token = request.form.get("token") or (request.json or {}).get("token")
    if not token: abort(400, "Missing token")
    try:
        data = signer.loads(token, max_age=app.config["TOKEN_MAX_AGE_SECONDS"])
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
        import traceback
        traceback.print_exc()
        # Error is already stored in database by create_order_from_offer

    return jsonify({"status":"ok", "message":"Consent recorded", "agreed_at": now})

@app.post("/api/reject")
def api_reject():
    token = request.form.get("token") or (request.json or {}).get("token")
    if not token: abort(400, "Missing token")
    try:
        data = signer.loads(token, max_age=app.config["TOKEN_MAX_AGE_SECONDS"])
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
        data = signer.loads(token, max_age=app.config["TOKEN_MAX_AGE_SECONDS"])
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
        import traceback
        traceback.print_exc()
        # Error is already stored in database by create_order_from_offer

    return render_template("accepted.html", offer=offer, when=now, already=False)


# --------- Page: Reject (renders HTML) ----------
@app.post("/reject")
def reject_page():
    token = request.form.get("token") or (request.json or {}).get("token")
    if not token: return render_template("decision_error.html", title="Ошибка", message="Отсутствует токен."), 400

    try:
        data = signer.loads(token, max_age=app.config["TOKEN_MAX_AGE_SECONDS"])
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
def _post_order(url: str, payload: dict, timeout: int, idem_key: str):
    from flask import current_app
    api_key = current_app.config.get("ORDER_API_KEY")
    if not api_key:
        raise ValueError("ORDER_API_KEY is not configured. Please set ORDER_API_KEY in your .env file.")
    
    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        retry=retry_if_exception_type((requests.Timeout, requests.ConnectionError))
    )
    def _inner():
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "AUTHORIZATION": f"Bearer {api_key}",
            "Idempotency-Key": idem_key
        }
        return requests.post(url, json=payload, headers=headers, timeout=timeout)
    return _inner()


def create_order_from_offer(link_id: int):
    with db() as conn:
        c = conn.cursor()
        c.execute("""SELECT l.*, u.filial_id, u.customer_account_id, u.phone, u.id AS uid,
                            o.product_offer_id, o.product_offer_struct_id, o.po_struct_element_id,
                            o.product_num, o.resource_spec_id, o.details_json
                     FROM links l
                       JOIN users u ON u.id=l.user_id
                       JOIN offers o ON o.id=l.offer_id
                     WHERE l.id=?""", (link_id,))
        row = c.fetchone()
        if not row: return

        # Convert Row to dict for easier access
        row_dict = dict(row)
        
        # Get address from link, fallback to default if not available
        address = {"STREET_ID": 123, "HOUSE": 1, "ZIP_CODE": "050000"}
        if row_dict.get("address_json"):
            try:
                stored_address = json.loads(row_dict["address_json"])
                address.update(stored_address)
            except (json.JSONDecodeError, TypeError):
                pass

        base_external_id = row_dict["external_id"] or f"LNK-{link_id}"
        action_date = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.000")
        
        # Try to get cust_order_items from details_json
        cust_order_items = None
        if row_dict.get("details_json"):
            try:
                details = json.loads(row_dict["details_json"])
                cust_order_items = details.get("cust_order_items")
                print(f"DEBUG: Retrieved cust_order_items from details_json: {json.dumps(cust_order_items, indent=2, ensure_ascii=False)}")
            except (json.JSONDecodeError, AttributeError) as e:
                print(f"DEBUG: Error parsing details_json: {e}")
                pass
        
        # Build CUST_ORDER_ITEMS
        if cust_order_items and len(cust_order_items) > 0:
            # Use configured cust_order_items
            order_items = []
            for item in cust_order_items:
                # Replace placeholders in EXTERNAL_ID
                external_id = item.get("external_id", "").replace("{link_external_id}", base_external_id)
                if not external_id:
                    external_id = f"{base_external_id}-{item.get('order_num', 1)}"
                
                # Build PO_STRUCT_ELEMENTS with auto-generated ACTION_DATE
                po_elements = []
                po_struct_elements_raw = item.get("po_struct_elements", [])
                print(f"DEBUG: Processing item {item.get('order_num')}, po_struct_elements: {po_struct_elements_raw}")
                for elem in po_struct_elements_raw:
                    po_struct_element_id = elem.get("po_struct_element_id")
                    if po_struct_element_id is not None:
                        po_elements.append({
                            "PO_STRUCT_ELEMENT_ID": po_struct_element_id,
                            "ACTION_DATE": action_date,
                            "SERVICE_COUNT": elem.get("service_count", 1)
                        })
                    else:
                        print(f"DEBUG: Skipping element with None po_struct_element_id: {elem}")
                print(f"DEBUG: Built {len(po_elements)} PO_STRUCT_ELEMENTS for item {item.get('order_num')}")
                
                order_item = {
                    "EXTERNAL_ID": external_id,
                    "ORDER_NUM": item.get("order_num", 1),
                    "PO_COMPONENT_ID": item.get("po_component_id"),
                    "PRODUCT_OFFER_STRUCT_ID": item.get("product_offer_struct_id"),
                    "SERVICE_COUNT": item.get("service_count", 1),
                    "PO_STRUCT_ELEMENTS": po_elements
                }
                # Only add if it has required fields
                if order_item["PRODUCT_OFFER_STRUCT_ID"] is not None or po_elements:
                    order_items.append(order_item)
            
            if order_items:
                cust_order_items_payload = order_items
            else:
                # Fall back to default if no valid items
                cust_order_items_payload = None
        else:
            # Fall back to default single-item structure
            cust_order_items_payload = None
        
        # Use fallback if no cust_order_items configured
        if cust_order_items_payload is None:
            cust_order_items_payload = [{
                "EXTERNAL_ID": f"{base_external_id}-1",
                "ORDER_NUM": 1,
                "PO_COMPONENT_ID": -1,
                "PRODUCT_OFFER_STRUCT_ID": row_dict.get("product_offer_struct_id"),
                "PRODUCT_NUM": row_dict.get("product_num"),
                "RESOURCE_SPEC_ID": row_dict.get("resource_spec_id"),
                "SERVICE_COUNT": 1,
                "PO_STRUCT_ELEMENTS": [{
                    "PO_STRUCT_ELEMENT_ID": row_dict.get("po_struct_element_id"),
                    "ACTION_DATE": action_date,
                    "SERVICE_COUNT": 1
                }] if row_dict.get("po_struct_element_id") else []
            }]

        payload = {
            "FILIAL_ID": row_dict.get("filial_id") or 17,
            "CUSTOMER_ACCOUNT_ID": row_dict.get("customer_account_id"),
            "SALES_CHANNEL_ID": 1,
            "EXTERNAL_ID": base_external_id,
            "PRODUCT_OFFER_ID": row_dict.get("product_offer_id"),
            "ADDRESS": address,
            "CUST_ORDER_ITEMS": cust_order_items_payload
        }
        
        # Add ORDER_CONTACT_PHONE if phone is available
        phone = row_dict.get("phone")
        if phone:
            # Remove .0 suffix if phone was stored as float (e.g., "77089244226.0" -> "77089244226")
            phone_str = str(phone).strip()
            if phone_str.endswith('.0'):
                phone_str = phone_str[:-2]
            payload["ORDER_CONTACT_PHONE"] = phone_str
        from flask import current_app
        order_api_url = current_app.config["ORDER_API_URL"]
        order_api_timeout = current_app.config["ORDER_API_TIMEOUT"]
        
        print("Posting Order:", order_api_url)
        print("Order payload:", json.dumps(payload, indent=2, ensure_ascii=False))
        
        # Store request data for debugging
        request_data = {
            "url": order_api_url,
            "method": "POST",
            "payload": payload,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        try:
            r = _post_order(
                    order_api_url,
                payload,
                    order_api_timeout,
                idem_key=f"link-order-{link_id}"
            )
            print("Order response:", r.status_code, r.text)
            
            # Parse response JSON to check for ORDER_ID
            response_json = None
            try:
                response_json = r.json()
            except (ValueError, AttributeError):
                pass  # Response is not JSON
            
            # Determine success: must have ORDER_ID with a value in the response
            success = False
            if response_json and isinstance(response_json, dict):
                order_id = response_json.get("ORDER_ID")
                # Success if ORDER_ID exists and has a truthy value
                success = order_id is not None and order_id != "" and order_id != 0
            elif r.status_code < 400:
                # Fallback: if no JSON but status is OK, consider it success
                # (though ideally we should have ORDER_ID)
                success = True
            
            # Store request and response in database
            response_data = {
                "request": request_data,
                "status_code": r.status_code,
                "response_text": r.text,
                "timestamp": datetime.datetime.now().isoformat(),
                "success": success
            }
            if response_json:
                response_data["response_json"] = response_json
            
            # Store response using the existing connection
            c.execute("UPDATE links SET order_response_json=? WHERE id=?", 
                     (json.dumps(response_data, ensure_ascii=False), link_id))
            conn.commit()
            
            r.raise_for_status()
        except Exception as e:
            # Store error response with request data using existing connection
            error_data = {
                "request": request_data,
                "error": str(e),
                "error_type": type(e).__name__,
                "timestamp": datetime.datetime.now().isoformat(),
                "success": False
            }
            try:
                c.execute("UPDATE links SET order_response_json=? WHERE id=?", 
                         (json.dumps(error_data, ensure_ascii=False), link_id))
                conn.commit()
            except Exception as db_err:
                print(f"Failed to store error in database: {db_err}")
                # Try with a new connection as fallback
                try:
                    with db() as conn2:
                        c2 = conn2.cursor()
                        c2.execute("UPDATE links SET order_response_json=? WHERE id=?", 
                                 (json.dumps(error_data, ensure_ascii=False), link_id))
                        conn2.commit()
                except Exception:
                    pass  # Don't fail if we can't store the error
            raise


# ---------- Health ----------
# in app.py (or wherever you create app = Flask(__name__))
@app.get("/healthz")
def healthz():
    return {"status": "ok"}, 200

if __name__ == "__main__":
    app.run(debug=True)
