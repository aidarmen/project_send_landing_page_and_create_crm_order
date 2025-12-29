import os, io, csv, json, datetime
import pandas as pd
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, abort, session, jsonify
from dateutil import parser as dateparser
from db import db, now_iso, fetch_offer_snapshot
from itsdangerous import URLSafeTimedSerializer

bp = Blueprint("admin", __name__, url_prefix="/admin")

def link_url(base_url, token, phone=None):
    """Generate link URL"""
    return f"{base_url}/l/{token}"

def create_token(signer: URLSafeTimedSerializer, link_id: int) -> str:
    return signer.dumps({"lid": link_id})

# Admin authentication
def require_admin():
    """Check if user is authenticated as admin"""
    return session.get("admin_authenticated", False)

@bp.before_request
def check_admin_auth():
    """Require authentication for all admin routes except login"""
    if request.endpoint and request.endpoint.startswith("admin."):
        if request.endpoint != "admin.login" and request.endpoint != "admin.login_post":
            if not require_admin():
                return redirect(url_for("admin.login"))

# ---------- Admin Login ----------
@bp.get("/login")
def login():
    """Admin login page"""
    if require_admin():
        return redirect(url_for("admin.dashboard"))
    return render_template("admin/login.html")

@bp.post("/login")
def login_post():
    """Handle admin login"""
    from dotenv import load_dotenv
    # Ensure .env is loaded (in case it wasn't loaded when module was imported)
    load_dotenv()
    
    password = request.form.get("password", "").strip()
    admin_password = os.getenv("ADMIN_PASSWORD", "admin").strip()
    
    # Debug: print to console (remove in production)
    print(f"DEBUG: Attempting login. Password length: {len(password)}, Admin password length: {len(admin_password)}")
    print(f"DEBUG: Admin password from env: {repr(admin_password)}")
    
    if password == admin_password:
        session["admin_authenticated"] = True
        flash("Успешный вход", "success")
        return redirect(url_for("admin.dashboard"))
    else:
        flash("Неверный пароль", "danger")
        return redirect(url_for("admin.login"))

@bp.get("/logout")
def logout():
    """Admin logout"""
    session.pop("admin_authenticated", None)
    flash("Вы вышли из системы", "info")
    return redirect(url_for("admin.login"))

def _to_int(x):
    try:
        return int(x) if x not in (None, "", "None") else None
    except: return None

def _to_bool(x):
    return str(x).lower() in ("1","true","yes","on")

# ---------- Dashboard ----------
@bp.get("/")
def dashboard():
    with db() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) AS n FROM users"); users = c.fetchone()["n"]
        c.execute("SELECT COUNT(*) AS n FROM offers"); offers = c.fetchone()["n"]
        c.execute("SELECT COUNT(*) AS n FROM links"); links = c.fetchone()["n"]
        c.execute("""SELECT status, COUNT(*) n FROM links GROUP BY status"""); stats = c.fetchall()
        # Agreements over last 30 days
        c.execute(
            """
            SELECT substr(created_at,1,10) AS d, COUNT(*) AS n
            FROM consents
            WHERE choice='AGREED' AND created_at >= datetime('now','-30 day')
            GROUP BY substr(created_at,1,10)
            ORDER BY d
            """
        )
        agree_rows = c.fetchall()
        agree_dates = [r["d"] for r in agree_rows]
        agree_counts = [r["n"] for r in agree_rows]
        c.execute("""SELECT bu.*, o.title AS offer_title
                     FROM bulk_uploads bu LEFT JOIN offers o ON o.id = bu.offer_id
                     ORDER BY bu.id DESC LIMIT 10""")
        uploads = c.fetchall()
        upload_labels = [f"#{u['id']}" for u in uploads]
        upload_totals = [u["count_total"] for u in uploads]
    return render_template(
        "admin/dashboard.html",
        users=users,
        offers=offers,
        links=links,
        stats=stats,
        uploads=uploads,
        agree_dates=agree_dates,
        agree_counts=agree_counts,
        upload_labels=upload_labels,
        upload_totals=upload_totals,
    )

# ---------- Offers CRUD ----------
@bp.get("/offers")
def offers_list():
    with db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM offers ORDER BY id DESC")
        rows = c.fetchall()
    return render_template("admin/offers_list.html", rows=rows)

@bp.get("/offers/new")
def offer_new():
    # for new offer we pass empty details+comp map
    return render_template("admin/offer_form.html", row=None, details={}, comp={}, badge_text="", cust_order_items=[])

@bp.get("/offers/<int:oid>/edit")
def offer_edit(oid):
    with db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM offers WHERE id=?", (oid,))
        row = c.fetchone()
        if not row: abort(404)
        # Parse details_json
        try:
            details = json.loads(row["details_json"] or "{}")
        except Exception:
            details = {}
        comp_map = { (c.get("type") or f"t{i}"): c for i,c in enumerate(details.get("components", [])) }
        # readable badges for the small text input
        badge_text = ", ".join(details.get("badges", []))
        # extract cust_order_items
        cust_order_items = details.get("cust_order_items", [])
    
    # Get debug messages from session if available
    debug_messages = session.pop('offer_save_debug', None)
    
    return render_template("admin/offer_form.html", row=row, details=details, comp=comp_map, badge_text=badge_text, cust_order_items=cust_order_items, debug_messages=debug_messages)

@bp.post("/offers/save")
def offer_save():
    f = request.form

    # Build components based on toggles
    components = []
    # Basic validation
    errors = []
    bundle_allowed = {"internet", "fms", "tv", "bundle"}
    if not f.get("title"):
        errors.append("Название обязательно")
    if f.get("bundle") not in bundle_allowed:
        errors.append("Некорректный тип пакета")
    try:
        if f.get("price"):
            if float(f.get("price")) < 0:
                errors.append("Цена не может быть отрицательной")
    except Exception:
        errors.append("Цена должна быть числом")
    if errors:
        for e in errors:
            flash(e, "danger")
        return redirect(url_for("admin.offer_new") if not f.get("id") else url_for("admin.offer_edit", oid=f.get("id")))

    if f.get("has_internet"):
        components.append({
            "type": "internet",
            "title": f.get("internet_title") or "Домашний интернет",
            "max_speed_mbps": _to_int(f.get("internet_max_speed_mbps")),
        })

    if f.get("has_tv"):
        ott = [s.strip() for s in (f.get("tv_ott") or "").split(",") if s.strip()]
        components.append({
            "type": "tv",
            "title": f.get("tv_title") or "Телевидение, фильмы и сериалы",
            "channels": _to_int(f.get("tv_channels")),
            "ott": ott
        })

    if f.get("has_mobile"):
        components.append({
            "type": "mobile",
            "title": f.get("mobile_title") or "Мобильная связь",
            "sims": _to_int(f.get("mobile_sims")),
            "data_gb": _to_int(f.get("mobile_data_gb")),
            "after_cap_kbps": _to_int(f.get("mobile_after_cap_kbps")),
            "onnet_minutes": _to_int(f.get("mobile_onnet_minutes")),
            "offnet_minutes": _to_int(f.get("mobile_offnet_minutes")),
            "sms": _to_int(f.get("mobile_sms")),
            "tv_plus_included": _to_bool(f.get("mobile_tv_plus_included"))
        })

    if f.get("has_home_phone"):
        components.append({
            "type": "home_phone",
            "title": f.get("phone_title") or "Домашний телефон",
            "onnet_minutes": _to_int(f.get("phone_onnet_minutes")),
            "offnet_minutes": _to_int(f.get("phone_offnet_minutes"))
        })

    if f.get("has_sim_devices"):
        components.append({
            "type": "sim_devices",
            "title": f.get("iot_title") or "SIM для устройств",
            "sims": _to_int(f.get("iot_sims")),
            "data_gb": _to_int(f.get("iot_data_gb")),
            "after_cap_kbps": _to_int(f.get("iot_after_cap_kbps"))
        })

    badges = [s.strip() for s in (f.get("badge_text") or "").split(",") if s.strip()]
    details = { "badges": badges, "components": components }

    # Parse cust_order_items from form
    cust_order_items = []
    item_indices = set()
    
    # Debug: Collect debug messages to show on the form page
    debug_messages = []
    
    # Debug: Show all form keys related to po_struct_elements
    po_struct_keys = [k for k in f.keys() if 'po_struct_elements' in k]
    if po_struct_keys:
        print(f"DEBUG: Found {len(po_struct_keys)} form keys with 'po_struct_elements': {po_struct_keys[:5]}...")  # Show first 5
        debug_messages.append(f"Found {len(po_struct_keys)} form fields for PO_STRUCT_ELEMENTS")
    else:
        print("DEBUG: No form keys found with 'po_struct_elements'")
        debug_messages.append("WARNING: No PO_STRUCT_ELEMENTS form fields found")
    
    # Find all item indices from form keys
    for key in f.keys():
        if key.startswith("cust_order_items[") and "][" in key:
            # Extract item index: cust_order_items[0][external_id] -> 0
            try:
                idx_str = key.split("[")[1].split("]")[0]
                item_indices.add(int(idx_str))
            except (ValueError, IndexError):
                continue
    
    # Build cust_order_items array
    for item_idx in sorted(item_indices):
        item = {
            "external_id": f.get(f"cust_order_items[{item_idx}][external_id]", "").strip(),
            "order_num": _to_int(f.get(f"cust_order_items[{item_idx}][order_num]")),
            "po_component_id": _to_int(f.get(f"cust_order_items[{item_idx}][po_component_id]")),
            "product_offer_struct_id": _to_int(f.get(f"cust_order_items[{item_idx}][product_offer_struct_id]")),
            "service_count": _to_int(f.get(f"cust_order_items[{item_idx}][service_count]")),
            "po_struct_elements": []
        }
        
        # Find all element indices for this item
        elem_indices = set()
        prefix = f"cust_order_items[{item_idx}][po_struct_elements]["
        print(f"DEBUG: Looking for keys starting with '{prefix}'")
        matching_keys = [k for k in f.keys() if k.startswith(prefix)]
        print(f"DEBUG: Item {item_idx} - Found {len(matching_keys)} keys matching prefix: {matching_keys}")
        
        for key in f.keys():
            if key.startswith(prefix):
                try:
                    # Extract element index: cust_order_items[0][po_struct_elements][1][po_struct_element_id] -> 1
                    # Remove the prefix to get: 1][po_struct_element_id]
                    remaining = key[len(prefix):]
                    elem_idx_str = remaining.split("]")[0]
                    print(f"DEBUG: Parsing key '{key}' - remaining: '{remaining}', elem_idx_str: '{elem_idx_str}'")
                    if elem_idx_str.isdigit():
                        elem_indices.add(int(elem_idx_str))
                        print(f"DEBUG: Added element index {elem_idx_str} from key '{key}'")
                    else:
                        print(f"DEBUG: elem_idx_str '{elem_idx_str}' is not a digit, skipping")
                except (ValueError, IndexError) as e:
                    print(f"DEBUG: Error parsing element index from key '{key}': {e}")
                    continue
        
        # Debug: print found element indices
        elem_indices_sorted = sorted(elem_indices)
        print(f"DEBUG: Item {item_idx} - Found element indices: {elem_indices_sorted}")
        if not elem_indices_sorted:
            debug_messages.append(f"Item {item_idx}: No PO_STRUCT_ELEMENTS found in form data")
        
        # Build po_struct_elements array
        for elem_idx in elem_indices_sorted:
            po_struct_element_id_key = f"cust_order_items[{item_idx}][po_struct_elements][{elem_idx}][po_struct_element_id]"
            service_count_key = f"cust_order_items[{item_idx}][po_struct_elements][{elem_idx}][service_count]"
            
            po_struct_element_id_val = f.get(po_struct_element_id_key)
            service_count_val = f.get(service_count_key)
            
            print(f"DEBUG: Element {elem_idx} - po_struct_element_id: '{po_struct_element_id_val}' (raw), service_count: '{service_count_val}' (raw)")
            
            element = {
                "po_struct_element_id": _to_int(po_struct_element_id_val),
                "service_count": _to_int(service_count_val)
            }
            
            print(f"DEBUG: Element {elem_idx} - po_struct_element_id: {element['po_struct_element_id']} (parsed), service_count: {element['service_count']} (parsed)")
            
            # Only add if po_struct_element_id is provided
            if element["po_struct_element_id"] is not None:
                item["po_struct_elements"].append(element)
                print(f"DEBUG: Added element {elem_idx} to item {item_idx}")
            else:
                print(f"DEBUG: Skipped element {elem_idx} - po_struct_element_id is None")
                debug_messages.append(f"Item {item_idx}, Element {elem_idx}: Skipped (po_struct_element_id is empty)")
        
        print(f"DEBUG: Item {item_idx} - Final po_struct_elements count: {len(item['po_struct_elements'])}")
        
        # Only add item if it has at least external_id or product_offer_struct_id
        if item["external_id"] or item["product_offer_struct_id"] is not None:
            cust_order_items.append(item)
    
    if cust_order_items:
        details["cust_order_items"] = cust_order_items
        total_elements = sum(len(item.get('po_struct_elements', [])) for item in cust_order_items)
        debug_msg = f"Saving {len(cust_order_items)} order item(s) with {total_elements} PO_STRUCT_ELEMENTS total"
        print(debug_msg)
        print(f"DEBUG: Final cust_order_items to save: {json.dumps(cust_order_items, indent=2, ensure_ascii=False)}")
        debug_messages.append(debug_msg)
        # Show detailed info for each item
        for idx, item in enumerate(cust_order_items):
            elem_count = len(item.get('po_struct_elements', []))
            debug_messages.append(f"Item {idx+1}: {elem_count} PO_STRUCT_ELEMENTS")
    else:
        print("DEBUG: No cust_order_items to save")
        debug_messages.append("WARNING: No cust_order_items to save")

    with db() as conn:
        c = conn.cursor()
        if f.get("id"):
            c.execute("""UPDATE offers SET
                           title=?, bundle=?, price=?, currency=?, details_json=?,
                           product_offer_id=?, product_offer_struct_id=?, po_struct_element_id=?, product_num=?, resource_spec_id=?
                         WHERE id=?""",
                      (f["title"], f["bundle"],
                       f.get("price") or None, f.get("currency") or "₸",
                       json.dumps(details, ensure_ascii=False),
                       f.get("product_offer_id") or None, f.get("product_offer_struct_id") or None,
                       f.get("po_struct_element_id") or None, f.get("product_num") or None,
                       f.get("resource_spec_id") or None, f["id"]))
            
            # Automatically update snapshots for active links (NEW/OPENED status)
            offer_id = int(f["id"])
            snap = fetch_offer_snapshot(c, offer_id)
            if snap:
                c.execute("""UPDATE links 
                             SET offer_snapshot_json = ?
                             WHERE offer_id = ? AND status IN ('NEW', 'OPENED')""",
                          (json.dumps(snap, ensure_ascii=False), offer_id))
                updated_count = c.rowcount
                if updated_count > 0:
                    debug_messages.append(f"✅ Автоматически обновлено {updated_count} активных ссылок (NEW/OPENED) с новым заголовком и данными предложения")
            
            conn.commit()
            # Store debug messages in session for display on the form
            session['offer_save_debug'] = debug_messages
            # Stay on edit page when editing
            return redirect(url_for("admin.offer_edit", oid=f["id"]))
        else:
            c.execute("""INSERT INTO offers
                           (title, bundle, price, currency, details_json,
                            product_offer_id, product_offer_struct_id, po_struct_element_id, product_num, resource_spec_id)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                      (f["title"], f["bundle"],
                       f.get("price") or None, f.get("currency") or "₸",
                       json.dumps(details, ensure_ascii=False),
                       f.get("product_offer_id") or None, f.get("product_offer_struct_id") or None,
                       f.get("po_struct_element_id") or None, f.get("product_num") or None,
                       f.get("resource_spec_id") or None))
            conn.commit()
            oid = c.lastrowid
            # Store debug messages in session for display on the form
            session['offer_save_debug'] = debug_messages
            # Redirect to edit page for new offers too
            return redirect(url_for("admin.offer_edit", oid=oid))

@bp.post("/offers/<int:oid>/delete")
def offer_delete(oid):
    with db() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM offers WHERE id=?", (oid,))
        conn.commit()
    flash("Offer deleted", "info")
    return redirect(url_for("admin.offers_list"))

# ---------- Uploads ----------
@bp.get("/uploads")
def uploads_list():
    with db() as conn:
        c = conn.cursor()
        c.execute("""SELECT bu.*, o.title as offer_title
                     FROM bulk_uploads bu LEFT JOIN offers o ON o.id=bu.offer_id
                     ORDER BY bu.id DESC""")
        rows = c.fetchall()
    return render_template("admin/uploads_list.html", rows=rows)

@bp.get("/uploads/new")
def upload_form():
    with db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM offers ORDER BY id DESC")
        offers = c.fetchall()
    return render_template("admin/upload_form.html", offers=offers)

@bp.post("/uploads/new")
def upload_new():
    file = request.files.get("file")
    offer_id = int(request.form.get("offer_id"))
    try:
        expires_in_days = int(request.form.get("expires_in_days", "7"))
    except Exception:
        expires_in_days = 7
    if expires_in_days <= 0:
        expires_in_days = 7
    external_prefix = request.form.get("external_prefix") or "BATCH"

    if not file or not file.filename:
        flash("Please choose a CSV or Excel file.", "danger")
        return redirect(url_for("admin.upload_form"))

    filename = file.filename
    try:
        if filename.lower().endswith(".csv"):
            # Read file content to handle encoding detection
            file.seek(0)
            file_content = file.read()
            
            # Try UTF-8 first, then Windows-1251 if it fails
            try:
                # Try to decode as UTF-8
                content_str = file_content.decode('utf-8')
                df = pd.read_csv(io.StringIO(content_str))
            except (UnicodeDecodeError, UnicodeError):
                try:
                    # Try Windows-1251 encoding
                    content_str = file_content.decode('windows-1251')
                    df = pd.read_csv(io.StringIO(content_str))
                except Exception as e:
                    flash(f"Failed to parse CSV file. Tried UTF-8 and Windows-1251. Error: {e}", "danger")
                    return redirect(url_for("admin.upload_form"))
        else:
            df = pd.read_excel(file)
    except Exception as e:
        flash(f"Failed to parse file: {e}", "danger")
        return redirect(url_for("admin.upload_form"))

    # Check for customer_account_id column (case insensitive)
    customer_col = None
    df_columns_lower = [c.lower().strip() for c in df.columns]
    for col in df.columns:
        if col.lower().strip() == "customer_account_id":
            customer_col = col
            break
    
    if not customer_col:
        available_cols = ", ".join([f"'{c}'" for c in df.columns[:10]])
        if len(df.columns) > 10:
            available_cols += f", ... ({len(df.columns)} total columns)"
        flash(f"File must contain 'customer_account_id' column. Found columns: {available_cols}", "danger")
        return redirect(url_for("admin.upload_form"))
    
    # Check for filial_id column (case insensitive)
    filial_col = None
    for col in df.columns:
        if col.lower().strip() == "filial_id":
            filial_col = col
            break
    
    if not filial_col:
        available_cols = ", ".join([f"'{c}'" for c in df.columns[:10]])
        if len(df.columns) > 10:
            available_cols += f", ... ({len(df.columns)} total columns)"
        flash(f"File must contain 'filial_id' column. Found columns: {available_cols}", "danger")
        return redirect(url_for("admin.upload_form"))
    
    # Check for required address columns in file
    address_columns = {
        "street_id": "STREET_ID",
        "house": "HOUSE",
        "sub_house": "SUB_HOUSE",
        "flat": "FLAT",
        "sub_flat": "SUB_FLAT",
        "zip_code": "ZIP_CODE"
    }
    required_address_cols = ["street_id", "house", "zip_code"]
    optional_address_cols = ["sub_house", "flat", "sub_flat"]
    
    # Check if required address columns exist (case insensitive)
    df_columns_lower = [c.lower() for c in df.columns]
    missing_cols = []
    for col in required_address_cols:
        if col.lower() not in df_columns_lower:
            missing_cols.append(col)
    
    if missing_cols:
        flash(f"File must contain required address columns: {', '.join(missing_cols)}", "danger")
        return redirect(url_for("admin.upload_form"))
    
    # Map Excel column names to API keys (case insensitive)
    column_mapping = {}
    for excel_col in address_columns.keys():
        for df_col in df.columns:
            if df_col.lower().strip() == excel_col.lower().strip():
                column_mapping[excel_col] = df_col
                break
    
    # Debug: Check if required address columns were found
    missing_address_cols = [col for col in required_address_cols if col not in column_mapping]
    if missing_address_cols:
        available_cols = ", ".join([f"'{c}'" for c in df.columns])
        flash(f"Warning: Some required address columns not found: {', '.join(missing_address_cols)}. Available columns: {available_cols}", "warning")

    # create bulk_upload record
    expires_at = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=expires_in_days)).isoformat()
    with db() as conn:
        c = conn.cursor()
        c.execute("""INSERT INTO bulk_uploads (filename, uploaded_at, offer_id, expires_at, count_total)
                     VALUES (?, ?, ?, ?, ?)""",
                  (filename, now_iso(), offer_id, expires_at, int(len(df))))
        upload_id = c.lastrowid

        # prepare offer snapshot
        snap = fetch_offer_snapshot(c, offer_id)
        if not snap:
            conn.rollback()
            flash("Offer not found.", "danger")
            return redirect(url_for("admin.upload_form"))

        # iterate customers
        created = 0
        row_counter = 0
        errors = []
        for idx, row_data in df.iterrows():
            row_counter += 1
            
            # Get customer_account_id value
            val = row_data.get(customer_col)
            
            # Debug: Show first row details if error
            if row_counter == 1 and (pd.isna(val) or val == "" or val is None):
                # Show available columns and first row data for debugging
                debug_info = f"Column '{customer_col}' found. First row value: {repr(val)}. Available columns: {list(df.columns)[:5]}"
                errors.append(f"Row {row_counter}: Missing customer_account_id. {debug_info}")
                continue
            
            if pd.isna(val) or val == "" or val is None:
                errors.append(f"Row {row_counter}: Missing customer_account_id (empty or NaN)")
                continue
            
            # Convert to string and clean
            val_str = str(val).strip()
            if not val_str or val_str.lower() in ['nan', 'none', 'null', '']:
                errors.append(f"Row {row_counter}: Missing customer_account_id (value: '{val}')")
                continue
            
            # Try to convert to integer (handle float values like 123.0)
            try:
                # First try as float to handle "123.0" cases, then convert to int
                customer_account_id = int(float(val_str))
            except (ValueError, TypeError) as e:
                errors.append(f"Row {row_counter}: Invalid customer_account_id (value: '{val}', type: {type(val).__name__}, error: {str(e)})")
                continue
            
            if customer_account_id <= 0:
                errors.append(f"Row {row_counter}: Invalid customer_account_id (must be positive, got: {customer_account_id})")
                continue
            
            # Get filial_id from Excel file
            filial_id_val = row_data.get(filial_col)
            if pd.isna(filial_id_val) or filial_id_val == "":
                errors.append(f"Row {row_counter}: Missing 'filial_id' for customer_account_id {customer_account_id}")
                continue
            try:
                filial_id = int(filial_id_val)
            except (ValueError, TypeError):
                errors.append(f"Row {row_counter}: Invalid 'filial_id' for customer_account_id {customer_account_id}")
                continue
            
            # Build address from Excel file (required for each user)
            address = {}
            for excel_col, api_key in address_columns.items():
                if excel_col in column_mapping:
                    df_col = column_mapping[excel_col]
                    val = row_data.get(df_col)
                    if pd.notna(val) and val != "" and str(val).strip().lower() not in ['nan', 'none', 'null']:
                        if api_key in ("STREET_ID", "HOUSE", "FLAT"):
                            try:
                                # Handle float values like 123.0
                                address[api_key] = int(float(str(val)))
                            except (ValueError, TypeError) as e:
                                errors.append(f"Row {row_counter}: Invalid '{excel_col}' value '{val}' for customer_account_id {customer_account_id} (must be a number)")
                                break
                        elif api_key == "ZIP_CODE":
                            # ZIP_CODE should be an integer stored as a string
                            try:
                                zip_int = int(float(str(val)))
                                address[api_key] = str(zip_int)
                            except (ValueError, TypeError) as e:
                                errors.append(f"Row {row_counter}: Invalid '{excel_col}' value '{val}' for customer_account_id {customer_account_id} (must be a number)")
                                break
                        else:
                            address[api_key] = str(val).strip() or None
                    elif excel_col in required_address_cols:
                        # Required field is missing for this row
                        val_repr = repr(val) if val is not None else "None"
                        errors.append(f"Row {row_counter}: Missing required address field '{excel_col}' for customer_account_id {customer_account_id} (column '{df_col}' value: {val_repr})")
                        break
                elif excel_col in required_address_cols:
                    # Column not found in file
                    errors.append(f"Row {row_counter}: Required address column '{excel_col}' not found in file for customer_account_id {customer_account_id}")
                    break
            
            # If we hit an error in the loop above, skip this row
            if any(f"Row {row_counter}" in err and customer_account_id in err for err in errors[-3:]):
                continue
            
            # Validate required fields are present
            if "STREET_ID" not in address or address["STREET_ID"] is None:
                street_val = row_data.get(column_mapping.get("street_id", "N/A"), "N/A")
                errors.append(f"Row {row_counter}: Missing or invalid 'street_id' for customer_account_id {customer_account_id} (found value: {repr(street_val)})")
                continue
            if "HOUSE" not in address or address["HOUSE"] is None:
                house_val = row_data.get(column_mapping.get("house", "N/A"), "N/A")
                errors.append(f"Row {row_counter}: Missing or invalid 'house' for customer_account_id {customer_account_id} (found value: {repr(house_val)})")
                continue
            if "ZIP_CODE" not in address or not address["ZIP_CODE"]:
                zip_val = row_data.get(column_mapping.get("zip_code", "N/A"), "N/A")
                errors.append(f"Row {row_counter}: Missing or invalid 'zip_code' for customer_account_id {customer_account_id} (found value: {repr(zip_val)})")
                continue
            
            # Clean up None values for optional fields
            if address.get("SUB_HOUSE") is None:
                address.pop("SUB_HOUSE", None)
            if address.get("FLAT") is None:
                address.pop("FLAT", None)
            if address.get("SUB_FLAT") is None:
                address.pop("SUB_FLAT", None)
            
            # Get phone from Excel file (if available)
            phone = None
            if "phone" in df.columns:
                phone_val = row_data.get("phone")
                if pd.notna(phone_val) and phone_val != "":
                    # Remove .0 suffix if phone was stored as float (e.g., 77089244226.0 -> 77089244226)
                    phone_str = str(phone_val).strip()
                    if phone_str.endswith('.0'):
                        phone_str = phone_str[:-2]
                    phone = phone_str
            
            # find or create user by customer_account_id
            c.execute("SELECT id, filial_id, phone FROM users WHERE customer_account_id=?", (customer_account_id,))
            u = c.fetchone()
            if u:
                user_id = u["id"]
                # Update filial_id if it has changed
                if u["filial_id"] != filial_id:
                    c.execute("UPDATE users SET filial_id=? WHERE id=?", (filial_id, user_id))
                # Update phone if provided and different
                if phone and u["phone"] != phone:
                    c.execute("UPDATE users SET phone=? WHERE id=?", (phone, user_id))
            else:
                c.execute("""INSERT INTO users (name, phone, email, filial_id, customer_account_id)
                             VALUES (?, ?, ?, ?, ?)""",
                          (None, phone, None, filial_id, customer_account_id))
                user_id = c.lastrowid

            # insert link row (token to be added after we know link_id)
            created_at = now_iso()
            c.execute("""INSERT INTO links (upload_id, user_id, offer_id, external_id,
                                            created_at, expires_at, status, offer_snapshot_json, address_json)
                         VALUES (?, ?, ?, ?, ?, ?, 'NEW', ?, ?)""",
                      (upload_id, user_id, offer_id, f"{external_prefix}-{upload_id}-{row_counter}",
                       created_at, expires_at, json.dumps(snap), json.dumps(address)))
            link_id = c.lastrowid

            created += 1

        # Check if any valid rows were processed
        if created == 0:
            conn.rollback()
            if errors:
                for err in errors[:10]:  # Show first 10 errors
                    flash(err, "danger")
                if len(errors) > 10:
                    flash(f"... and {len(errors) - 10} more errors", "danger")
            else:
                flash("No valid rows found in file. Please check the file format.", "danger")
            return redirect(url_for("admin.upload_form"))
        
        # Show errors but continue if some rows were valid
        if errors:
            for err in errors[:5]:  # Show first 5 errors
                flash(err, "warning")
            if len(errors) > 5:
                flash(f"... and {len(errors) - 5} more rows had errors", "warning")

        # fetch BASE_URL & signer from app config (via current_app later)
        conn.commit()

    flash(f"Upload created: {created} links queued (tokens will be assigned on first visit or via /admin/uploads/<id>).", "success")
    return redirect(url_for("admin.upload_detail", upload_id=upload_id))

@bp.get("/uploads/<int:upload_id>")
def upload_detail(upload_id):
    with db() as conn:
        c = conn.cursor()
        c.execute("""SELECT bu.*, o.title as offer_title
                     FROM bulk_uploads bu LEFT JOIN offers o ON o.id=bu.offer_id
                     WHERE bu.id=?""", (upload_id,))
        batch = c.fetchone()
        if not batch: abort(404)

        c.execute("""
          SELECT l.*, u.customer_account_id, u.phone, l.order_response_json
          FROM links l JOIN users u ON u.id=l.user_id
          WHERE l.upload_id=? ORDER BY l.id ASC
        """, (upload_id,))
        rows = c.fetchall()
        # Parse order_response_json for each row
        # Convert Row objects to dicts for easier manipulation
        rows_list = []
        for row in rows:
            row_dict = dict(row)
            # Check if order_response_json column exists and has a value
            # sqlite3.Row supports 'in' operator and indexing
            order_response_json = None
            if "order_response_json" in row_dict:
                order_response_json = row_dict["order_response_json"]
            elif hasattr(row, "keys") and "order_response_json" in row.keys():
                order_response_json = row["order_response_json"]
            
            if order_response_json and order_response_json.strip():
                try:
                    resp = json.loads(order_response_json)
                    row_dict["order_response"] = resp
                    # Format JSON for display
                    if resp.get("response_json"):
                        row_dict["order_response"]["response_json_formatted"] = json.dumps(resp["response_json"], ensure_ascii=False, indent=2)
                        # Extract ORDER_ID from response_json
                        if isinstance(resp["response_json"], dict):
                            row_dict["order_id"] = resp["response_json"].get("ORDER_ID")
                    # Format request payload for display
                    if resp.get("request") and resp["request"].get("payload"):
                        row_dict["order_response"]["request"]["payload_formatted"] = json.dumps(resp["request"]["payload"], ensure_ascii=False, indent=2)
                except (json.JSONDecodeError, TypeError) as e:
                    row_dict["order_response"] = {"error": f"Failed to parse response: {str(e)}", "raw": str(order_response_json)[:100]}
                    row_dict["order_id"] = None
            else:
                row_dict["order_response"] = None
                row_dict["order_id"] = None
            
            # Generate URL
            if row_dict.get("token"):
                base_url = request.url_root.strip("/")
                row_dict["link_url"] = link_url(base_url, row_dict["token"])
            else:
                row_dict["link_url"] = None
            
            rows_list.append(row_dict)
        rows = rows_list
    return render_template("admin/upload_detail.html", batch=batch, rows=rows)

@bp.get("/uploads/<int:upload_id>/download.csv")
def upload_download_csv(upload_id):
    # build CSV in-memory
    with db() as conn:
        c = conn.cursor()
        c.execute("""
          SELECT l.id, u.customer_account_id, l.external_id, l.created_at, l.expires_at, l.status,
                 l.opened_at, l.agreed_at, l.rejected_at, l.token, u.phone, l.order_response_json
          FROM links l JOIN users u ON u.id=l.user_id
          WHERE l.upload_id=?
          ORDER BY l.id
        """, (upload_id,))
        rows = c.fetchall()

    out = io.StringIO(newline="")
    # Excel hint: force semicolon separator
    out.write("sep=;\r\n")

    w = csv.writer(out, delimiter=";", lineterminator="\r\n")
    w.writerow(["link_id","customer_account_id","external_id","created_at","expires_at",
                "status","opened_at","agreed_at","rejected_at","order_id","url"])

    base_url = request.url_root.strip("/")
    for r in rows:
        # Convert Row to dict for easier access
        r_dict = dict(r)
        
        url = ""
        if r_dict.get("token"):
            url = link_url(base_url, r_dict['token'])
        
        # Extract ORDER_ID from order_response_json
        order_id = ""
        order_response_json = r_dict.get("order_response_json")
        if order_response_json:
            try:
                resp = json.loads(order_response_json)
                if resp.get("response_json") and isinstance(resp["response_json"], dict):
                    order_id = resp["response_json"].get("ORDER_ID", "")
            except (json.JSONDecodeError, TypeError):
                pass
        
        w.writerow([r_dict["id"], r_dict["customer_account_id"], r_dict["external_id"], r_dict["created_at"],
                    r_dict["expires_at"], r_dict["status"], r_dict["opened_at"], r_dict["agreed_at"], r_dict["rejected_at"], order_id, url])

    mem = io.BytesIO(out.getvalue().encode("utf-8-sig"))
    return send_file(mem, mimetype="text/csv", as_attachment=True,
                     download_name=f"upload_{upload_id}_links.csv")

# Utility to assign tokens to any rows that are missing them (e.g., immediately after upload)
@bp.post("/uploads/<int:upload_id>/assign_tokens")
def upload_assign_tokens(upload_id):
    from flask import current_app
    signer = current_app.config["SIGNER"]
    with db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, token FROM links WHERE upload_id=? ORDER BY id", (upload_id,))
        rows = c.fetchall()
        assigned = 0
        for r in rows:
            if r["token"]:
                continue
            token = signer.dumps({"lid": r["id"]})
            c.execute("UPDATE links SET token=? WHERE id=?", (token, r["id"]))
            assigned += 1
        conn.commit()
    flash(f"Assigned tokens to {assigned} rows.", "success")
    return redirect(url_for("admin.upload_detail", upload_id=upload_id))

# Update offer snapshot for all active links of an offer (to update price/other fields)
@bp.post("/offers/<int:offer_id>/update_snapshots")
def update_offer_snapshots(offer_id):
    """Update offer_snapshot_json for all active links (NEW/OPENED status) of a specific offer"""
    with db() as conn:
        c = conn.cursor()
        # Check if offer exists
        c.execute("SELECT id FROM offers WHERE id=?", (offer_id,))
        if not c.fetchone():
            flash("Offer not found", "danger")
            return redirect(url_for("admin.offers_list"))
        
        # Fetch new snapshot
        snap = fetch_offer_snapshot(c, offer_id)
        if not snap:
            flash("Failed to fetch offer snapshot", "danger")
            return redirect(url_for("admin.offers_list"))
        
        # Update all links with status NEW or OPENED (not yet agreed/rejected)
        c.execute("""UPDATE links 
                     SET offer_snapshot_json = ?
                     WHERE offer_id = ? AND status IN ('NEW', 'OPENED')""",
                  (json.dumps(snap, ensure_ascii=False), offer_id))
        updated = c.rowcount
        conn.commit()
    
    flash(f"Updated offer snapshot for {updated} active link(s). Links with status AGREED/REJECTED were not changed.", "success")
    return redirect(url_for("admin.offer_edit", oid=offer_id))

# Resend order API request for a specific link
@bp.post("/links/<int:link_id>/resend_order")
def resend_order(link_id):
    # Verify link exists and belongs to an upload
    with db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, upload_id, status FROM links WHERE id=?", (link_id,))
        link = c.fetchone()
        if not link:
            flash("Link not found", "danger")
            return redirect(url_for("admin.uploads_list"))
        
        upload_id = link["upload_id"]
        if not upload_id:
            flash("Link does not belong to an upload", "danger")
            return redirect(url_for("admin.uploads_list"))
    
    # Resend the order - import create_order_from_offer from app module
    try:
        # Import at function level - by the time this runs, app.py is fully loaded
        # Use importlib to avoid circular import issues
        import importlib
        import sys
        
        # Try to get the app module from sys.modules first (faster)
        app_module = sys.modules.get('app')
        if not app_module:
            # If not in sys.modules, import it
            app_module = importlib.import_module('app')
        
        if hasattr(app_module, 'create_order_from_offer'):
            create_order_from_offer = getattr(app_module, 'create_order_from_offer')
            create_order_from_offer(link_id=link_id)
            flash("Order resend initiated successfully", "success")
        else:
            flash(f"Error: create_order_from_offer not found in app module. Available: {[x for x in dir(app_module) if not x.startswith('_') and callable(getattr(app_module, x, None))]}", "danger")
    except Exception as e:
        flash(f"Error resending order: {str(e)}", "danger")
        import traceback
        traceback.print_exc()
    
    return redirect(url_for("admin.upload_detail", upload_id=upload_id))


