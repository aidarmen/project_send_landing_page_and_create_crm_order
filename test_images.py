#!/usr/bin/env python3
"""
Quick test script to check if images are loading correctly.
This creates a test offer and link so you can view the landing page.
"""

import os
import sys
from app import app, signer, db, now_iso
from datetime import datetime, timedelta

def create_test_data():
    """Create a test offer and link for testing images."""
    with app.app_context():
        with db() as conn:
            c = conn.cursor()
            
            # Check if test offer exists
            c.execute("SELECT id FROM offers WHERE title LIKE 'Test Offer%' LIMIT 1")
            offer = c.fetchone()
            
            if not offer:
                # Create test offer
                test_offer = {
                    "title": "Test Offer - Internet 100 Mbps",
                    "bundle": "internet",
                    "price": 5000,
                    "currency": "₸",
                    "details": {
                        "components": [
                            {
                                "type": "internet",
                                "title": "Домашний интернет",
                                "max_speed_mbps": 100
                            }
                        ]
                    },
                    "product_offer_id": 123456,
                    "product_offer_struct_id": 555,
                    "po_struct_element_id": 777,
                    "product_num": "TEST-001",
                    "resource_spec_id": 4444
                }
                
                import json
                c.execute("""INSERT INTO offers (title, bundle, price, currency, details_json,
                                                 product_offer_id, product_offer_struct_id, 
                                                 po_struct_element_id, product_num, resource_spec_id)
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                         (test_offer["title"], test_offer["bundle"], test_offer["price"],
                          test_offer["currency"], json.dumps(test_offer["details"]),
                          test_offer["product_offer_id"], test_offer["product_offer_struct_id"],
                          test_offer["po_struct_element_id"], test_offer["product_num"],
                          test_offer["resource_spec_id"]))
                offer_id = c.lastrowid
                print(f"✅ Created test offer (ID: {offer_id})")
            else:
                offer_id = offer["id"]
                print(f"✅ Using existing test offer (ID: {offer_id})")
            
            # Check if test user exists
            c.execute("SELECT id FROM users WHERE customer_account_id = 999999 LIMIT 1")
            user = c.fetchone()
            
            if not user:
                # Create test user
                c.execute("""INSERT INTO users (name, phone, email, filial_id, customer_account_id)
                             VALUES (?, ?, ?, ?, ?)""",
                         ("Test User", "+77001234567", "test@example.com", 17, 999999))
                user_id = c.lastrowid
                print(f"✅ Created test user (ID: {user_id})")
            else:
                user_id = user["id"]
                print(f"✅ Using existing test user (ID: {user_id})")
            
            # Create test link
            expires_at = (datetime.now(datetime.timezone.utc) + timedelta(days=7)).isoformat()
            
            # Get offer snapshot
            from db import fetch_offer_snapshot
            offer_snap = fetch_offer_snapshot(c, offer_id)
            if not offer_snap:
                print("❌ Could not fetch offer snapshot")
                return None
            
            import json
            c.execute("""INSERT INTO links (user_id, offer_id, external_id, created_at, 
                                           expires_at, status, offer_snapshot_json)
                         VALUES (?, ?, ?, ?, ?, 'NEW', ?)""",
                     (user_id, offer_id, f"TEST-{int(datetime.now().timestamp())}",
                      now_iso(), expires_at, json.dumps(offer_snap)))
            link_id = c.lastrowid
            
            # Create token
            token = signer.dumps({"lid": link_id})
            
            # Update link with token
            c.execute("UPDATE links SET token = ? WHERE id = ?", (token, link_id))
            conn.commit()
            
            url = f"http://localhost:5000/l/{token}"
            print(f"\n🎉 Test link created!")
            print(f"📋 Link ID: {link_id}")
            print(f"🔗 URL: {url}")
            print(f"\n💡 Open this URL in your browser to see the landing page with images!")
            
            return url

if __name__ == "__main__":
    print("=" * 60)
    print("🧪 IMAGE TESTING SCRIPT")
    print("=" * 60)
    print("\nThis script will create a test offer and link so you can")
    print("view the landing page and check if images are loading.\n")
    
    url = create_test_data()
    
    if url:
        print(f"\n📝 Next steps:")
        print(f"1. Make sure the Flask app is running (python app.py)")
        print(f"2. Open the URL above in your browser")
        print(f"3. Check if images are displaying correctly")
        print(f"\n💡 Note: Images will be hidden if they don't exist (this is expected)")
        print(f"   Add your images to static/images/ to see them!")

