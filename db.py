import os, sqlite3, json, datetime
from contextlib import contextmanager

# DB_PATH = "app.db"

# db.py
DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "app.db"))

def db():
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def init_db():
    with db() as conn:
        c = conn.cursor()
        # users (customer master)
        c.execute("""
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY,
          name TEXT,
          phone TEXT,
          email TEXT,
          filial_id INTEGER,
          customer_account_id INTEGER UNIQUE
        )""")

        # offers (product catalog)
        c.execute("""
        CREATE TABLE IF NOT EXISTS offers (
          id INTEGER PRIMARY KEY,
          title TEXT NOT NULL,
          bundle TEXT NOT NULL,      -- 'internet' | 'fms' | 'tv' | 'bundle'
          price NUMERIC,
          currency TEXT,
          details_json TEXT,
          product_offer_id INTEGER,
          product_offer_struct_id INTEGER,
          po_struct_element_id INTEGER,
          product_num TEXT,
          resource_spec_id INTEGER
        )""")

        # bulk uploads (a batch of suggested links)
        c.execute("""
        CREATE TABLE IF NOT EXISTS bulk_uploads (
          id INTEGER PRIMARY KEY,
          filename TEXT,
          uploaded_at TEXT,
          offer_id INTEGER,
          expires_at TEXT,
          count_total INTEGER DEFAULT 0,
          notes TEXT,
          FOREIGN KEY(offer_id) REFERENCES offers(id)
        )""")

        # links (one per user/offer)
        c.execute("""
        CREATE TABLE IF NOT EXISTS links (
          id INTEGER PRIMARY KEY,
          upload_id INTEGER,
          user_id INTEGER,
          offer_id INTEGER,
          external_id TEXT,
          token TEXT UNIQUE,
          created_at TEXT,
          expires_at TEXT,
          opened_at TEXT,
          agreed_at TEXT,
          rejected_at TEXT,
          status TEXT DEFAULT 'NEW',    -- NEW | OPENED | AGREED | REJECTED | EXPIRED | USED
          offer_snapshot_json TEXT,
          FOREIGN KEY(user_id) REFERENCES users(id),
          FOREIGN KEY(offer_id) REFERENCES offers(id),
          FOREIGN KEY(upload_id) REFERENCES bulk_uploads(id)
        )""")

        # consents (audit trail)
        c.execute("""
        CREATE TABLE IF NOT EXISTS consents (
          id INTEGER PRIMARY KEY,
          link_id INTEGER,
          consent_text TEXT,
          choice TEXT,                -- 'AGREED' or 'REJECTED'
          created_at TEXT,
          ip TEXT,
          user_agent TEXT,
          FOREIGN KEY(link_id) REFERENCES links(id)
        )""")
        conn.commit()

def fetch_offer_snapshot(cur, offer_id: int):
    cur.execute("SELECT * FROM offers WHERE id=?", (offer_id,))
    o = cur.fetchone()
    if not o: return None
    d = dict(o)
    return {
        "id": d["id"],
        "title": d["title"],
        "bundle": d["bundle"],
        "price": d["price"],
        "currency": d["currency"],
        "details": json.loads(d["details_json"] or "{}"),
        "order_mapping": {
            "product_offer_id": d["product_offer_id"],
            "product_offer_struct_id": d["product_offer_struct_id"],
            "po_struct_element_id": d["po_struct_element_id"],
            "product_num": d["product_num"],
            "resource_spec_id": d["resource_spec_id"],
        }
    }
