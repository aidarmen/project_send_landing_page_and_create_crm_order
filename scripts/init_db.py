# scripts/init_db.py
import os, sqlite3, pathlib

# Where to create the DB (same as your project uses)
DB_PATH = os.environ.get("DB_PATH", os.path.join("data", "app.db"))
pathlib.Path(os.path.dirname(DB_PATH)).mkdir(parents=True, exist_ok=True)

SCHEMA = r"""
PRAGMA foreign_keys = ON;

-- Drop existing (safe re-init)
DROP TABLE IF EXISTS links;
DROP TABLE IF EXISTS uploads;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS offers;

-- Product offers (flexible, component-based)
CREATE TABLE offers (
  id                      INTEGER PRIMARY KEY AUTOINCREMENT,
  title                   TEXT NOT NULL,
  bundle                  TEXT NOT NULL,              -- 'internet' | 'tv' | 'mobile' | 'bundle' etc.
  price                   INTEGER,
  currency                TEXT,
  badge_text              TEXT,                       -- comma separated badges
  components_json         TEXT,                       -- JSON: { internet:{...}, tv:{...}, mobile:{...}, home_phone:{...}, sim_devices:{...} }
  product_offer_id        TEXT,
  product_offer_struct_id TEXT,
  po_struct_element_id    TEXT,
  product_num             TEXT,
  resource_spec_id        TEXT,
  created_at              TEXT DEFAULT (datetime('now')),
  updated_at              TEXT
);

-- Customers (dedup by customer_account_id)
CREATE TABLE users (
  id                   INTEGER PRIMARY KEY AUTOINCREMENT,
  name                 TEXT,
  phone                TEXT,
  email                TEXT,
  filial_id            INTEGER,
  customer_account_id  INTEGER UNIQUE,
  created_at           TEXT DEFAULT (datetime('now'))
);

-- Upload batches (per CSV/XLSX import)
CREATE TABLE uploads (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  filename     TEXT,
  offer_id     INTEGER NOT NULL REFERENCES offers(id) ON DELETE CASCADE,
  uploaded_at  TEXT DEFAULT (datetime('now')),
  expires_at   TEXT,
  count_total  INTEGER DEFAULT 0
);

-- Unique links per customer per upload
CREATE TABLE links (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  upload_id        INTEGER NOT NULL REFERENCES uploads(id) ON DELETE CASCADE,
  user_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  offer_id         INTEGER NOT NULL REFERENCES offers(id) ON DELETE CASCADE,
  external_id      TEXT,
  token            TEXT UNIQUE,            -- null until assigned
  status           TEXT DEFAULT 'pending', -- pending|opened|agreed|rejected|expired
  created_at       TEXT DEFAULT (datetime('now')),
  expires_at       TEXT,
  opened_at        TEXT,
  agreed_at        TEXT,
  rejected_at      TEXT
);

CREATE INDEX IF NOT EXISTS idx_links_token  ON links(token);
CREATE INDEX IF NOT EXISTS idx_links_upload ON links(upload_id);
CREATE INDEX IF NOT EXISTS idx_users_customer_account ON users(customer_account_id);
"""

def main():
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA)
        conn.commit()
    print(f"[ok] Initialized fresh DB at {DB_PATH}")

if __name__ == "__main__":
    main()
