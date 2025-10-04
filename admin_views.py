import os, io, csv, json, datetime
import pandas as pd
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, abort
from dateutil import parser as dateparser
from db import db, now_iso, fetch_offer_snapshot
from itsdangerous import URLSafeTimedSerializer

bp = Blueprint("admin", __name__, url_prefix="/admin")

def link_url(base_url, token):
    return f"{base_url}/l/{token}"

def create_token(signer: URLSafeTimedSerializer, link_id: int) -> str:
    return signer.dumps({"lid": link_id})

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
        c.execute("""SELECT bu.*, o.title AS offer_title
                     FROM bulk_uploads bu LEFT JOIN offers o ON o.id = bu.offer_id
                     ORDER BY bu.id DESC LIMIT 10""")
        uploads = c.fetchall()
    return render_template("admin/dashboard.html",
                           users=users, offers=offers, links=links, stats=stats, uploads=uploads)

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
    return render_template("admin/offer_form.html", row=None, details={}, comp={}, badge_text="")

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
    return render_template("admin/offer_form.html", row=row, details=details, comp=comp_map, badge_text=badge_text)

@bp.post("/offers/save")
def offer_save():
    f = request.form

    # Build components based on toggles
    components = []

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

    with db() as conn:
        c = conn.cursor()
        if f.get("id"):
            c.execute("""UPDATE offers SET
                           title=?, bundle=?, price=?, currency=?, details_json=?,
                           product_offer_id=?, product_offer_struct_id=?, po_struct_element_id=?, product_num=?, resource_spec_id=?
                         WHERE id=?""",
                      (f["title"], f["bundle"],
                       f.get("price") or None, f.get("currency") or "KZT",
                       json.dumps(details, ensure_ascii=False),
                       f.get("product_offer_id") or None, f.get("product_offer_struct_id") or None,
                       f.get("po_struct_element_id") or None, f.get("product_num") or None,
                       f.get("resource_spec_id") or None, f["id"]))
            conn.commit()
        else:
            c.execute("""INSERT INTO offers
                           (title, bundle, price, currency, details_json,
                            product_offer_id, product_offer_struct_id, po_struct_element_id, product_num, resource_spec_id)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                      (f["title"], f["bundle"],
                       f.get("price") or None, f.get("currency") or "KZT",
                       json.dumps(details, ensure_ascii=False),
                       f.get("product_offer_id") or None, f.get("product_offer_struct_id") or None,
                       f.get("po_struct_element_id") or None, f.get("product_num") or None,
                       f.get("resource_spec_id") or None))
            conn.commit()
    flash("Offer saved", "success")
    return redirect(url_for("admin.offers_list"))

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
    expires_in_days = int(request.form.get("expires_in_days", "7"))
    default_filial_id = int(request.form.get("default_filial_id", "17"))
    external_prefix = request.form.get("external_prefix") or "BATCH"

    if not file or not file.filename:
        flash("Please choose a CSV or Excel file.", "danger")
        return redirect(url_for("admin.upload_form"))

    filename = file.filename
    try:
        if filename.lower().endswith(".csv"):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
    except Exception as e:
        flash(f"Failed to parse file: {e}", "danger")
        return redirect(url_for("admin.upload_form"))

    if "customer_id" not in df.columns:
        flash("File must contain 'customer_id' column.", "danger")
        return redirect(url_for("admin.upload_form"))

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
        for i, val in enumerate(df["customer_id"].astype(str).tolist(), start=1):
            customer_account_id = int(val) if val.isdigit() else None
            if not customer_account_id:
                continue
            # find or create user by customer_account_id
            c.execute("SELECT id FROM users WHERE customer_account_id=?", (customer_account_id,))
            u = c.fetchone()
            if u:
                user_id = u["id"]
            else:
                c.execute("""INSERT INTO users (name, phone, email, filial_id, customer_account_id)
                             VALUES (?, ?, ?, ?, ?)""",
                          (None, None, None, default_filial_id, customer_account_id))
                user_id = c.lastrowid

            # insert link row (token to be added after we know link_id)
            created_at = now_iso()
            c.execute("""INSERT INTO links (upload_id, user_id, offer_id, external_id,
                                            created_at, expires_at, status, offer_snapshot_json)
                         VALUES (?, ?, ?, ?, ?, ?, 'NEW', ?)""",
                      (upload_id, user_id, offer_id, f"{external_prefix}-{upload_id}-{i}",
                       created_at, expires_at, json.dumps(snap)))
            link_id = c.lastrowid

            created += 1

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
          SELECT l.*, u.customer_account_id
          FROM links l JOIN users u ON u.id=l.user_id
          WHERE l.upload_id=? ORDER BY l.id ASC
        """, (upload_id,))
        rows = c.fetchall()
    return render_template("admin/upload_detail.html", batch=batch, rows=rows)

@bp.get("/uploads/<int:upload_id>/download.csv")
def upload_download_csv(upload_id):
    # build CSV in-memory
    with db() as conn:
        c = conn.cursor()
        c.execute("""
          SELECT l.id, u.customer_account_id, l.external_id, l.created_at, l.expires_at, l.status,
                 l.opened_at, l.agreed_at, l.rejected_at, l.token
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
                "status","opened_at","agreed_at","rejected_at","url"])

    base_url = request.url_root.strip("/")
    for r in rows:
        url = ""
        if r["token"]:
            url = f"{base_url}/l/{r['token']}"
        w.writerow([r["id"], r["customer_account_id"], r["external_id"], r["created_at"],
                    r["expires_at"], r["status"], r["opened_at"], r["agreed_at"], r["rejected_at"], url])

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

