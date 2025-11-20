#!/usr/bin/env python3
"""
Order Creation Script
Creates orders using the external API with the provided API key and user ID.
"""

import os
import sys
import json
import sqlite3
import requests
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from requests.adapters import HTTPAdapter, Retry

# =============================================================================
# CONFIGURATION
# =============================================================================

# API Configuration
API_KEY = "ItU2iuhEiYKeYl7ZVekueetugTU79mge"
BASE_URL = "http://10.8.219.66:8501"
CUSTOMER_ACCOUNT_ID = 12319534

# Database Configuration
DB_PATH = os.path.join("data", "app.db")  # Adjust path as needed

# Request Configuration
TIMEOUT = (5, 30)  # (connect, read) seconds
MAX_RETRIES = 3

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def setup_session() -> requests.Session:
    """Setup a robust session with retries."""
    session = requests.Session()
    retries = Retry(
        total=MAX_RETRIES,
        backoff_factor=0.4,
        status_forcelist=(500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "POST", "PUT", "DELETE", "PATCH"]),
    )
    session.mount("http://", HTTPAdapter(max_retries=retries))
    session.mount("https://", HTTPAdapter(max_retries=retries))
    return session

def get_headers() -> Dict[str, str]:
    """Get request headers with API key."""
    return {
        "Content-Type": "application/json",
        "AUTHORIZATION": API_KEY
    }

def pretty_json(data: Any) -> str:
    """Format data as pretty JSON."""
    try:
        return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
    except Exception:
        return str(data)

def handle_response(response: requests.Response) -> Tuple[int, str, Dict[str, Any]]:
    """Handle API response and extract error information."""
    try:
        payload = response.json()
    except ValueError:
        payload = {"raw": response.text}

    err_code = None
    err_msg = ""
    
    if isinstance(payload, dict):
        err_code = payload.get("ERR_CODE") or payload.get("errCode")
        err_msg = payload.get("ERR_MESSAGE") or payload.get("errMessage") or payload.get("ERRORMESSAGE") or ""
    
    if err_code is None:
        err_code = 0 if response.ok else response.status_code
        if not err_msg:
            err_msg = f"HTTP {response.status_code}"

    return err_code, err_msg, payload

# =============================================================================
# DATABASE FUNCTIONS
# =============================================================================

def get_user_info(customer_account_id: int) -> Optional[Dict[str, Any]]:
    """Get user information from database."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE customer_account_id = ?", (customer_account_id,))
            user = c.fetchone()
            return dict(user) if user else None
    except Exception as e:
        print(f"❌ Database error: {e}")
        return None

def get_offers() -> list:
    """Get all available offers from database."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT * FROM offers ORDER BY id")
            return [dict(row) for row in c.fetchall()]
    except Exception as e:
        print(f"❌ Database error: {e}")
        return []

# =============================================================================
# API FUNCTIONS
# =============================================================================

def create_new_order(session: requests.Session, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new order using the API."""
    url = f"{BASE_URL}/rest/oapi/order/create_new"
    
    print("🚀 Creating new order...")
    print(f"📡 URL: {url}")
    print("📋 Payload:")
    print(pretty_json(payload))
    
    try:
        response = session.post(
            url,
            json=payload,
            headers=get_headers(),
            timeout=TIMEOUT
        )
        
        err_code, err_msg, result = handle_response(response)
        
        print(f"\n📊 Response:")
        print(f"Status Code: {response.status_code}")
        print(pretty_json(result))
        
        if err_code == 0:
            print("✅ Order created successfully!")
            if "DATA" in result and "id" in result["DATA"]:
                print(f"🆔 Order ID: {result['DATA']['id']}")
        else:
            print(f"❌ API Error (Code: {err_code}): {err_msg}")
            
        return result
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return {"error": str(e)}

def create_work_order(session: requests.Session, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Create a work order using the API."""
    url = f"{BASE_URL}/rest/oapi/order/workOrder"
    
    print("🔧 Creating work order...")
    print(f"📡 URL: {url}")
    print("📋 Payload:")
    print(pretty_json(payload))
    
    try:
        response = session.post(
            url,
            json=payload,
            headers=get_headers(),
            timeout=TIMEOUT
        )
        
        err_code, err_msg, result = handle_response(response)
        
        print(f"\n📊 Response:")
        print(f"Status Code: {response.status_code}")
        print(pretty_json(result))
        
        if err_code == 0:
            print("✅ Work order created successfully!")
        else:
            print(f"❌ API Error (Code: {err_code}): {err_msg}")
            
        return result
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return {"error": str(e)}

# =============================================================================
# ORDER TEMPLATES
# =============================================================================

def create_basic_order_payload(customer_account_id: int, filial_id: int = 17) -> Dict[str, Any]:
    """Create a basic order payload."""
    external_id = f"EXT-{customer_account_id}-{int(datetime.now().timestamp())}"
    
    return {
        "FILIAL_ID": filial_id,
        "CUSTOMER_ACCOUNT_ID": customer_account_id,
        "SALES_CHANNEL_ID": 1,
        "EXTERNAL_ID": external_id,
        "PRODUCT_OFFER_ID": 123456,  # You need to specify the actual product offer ID
        "ADDRESS": {
            "STREET_ID": 123,
            "HOUSE": 1,
            "SUB_HOUSE": None,
            "FLAT": 1,
            "SUB_FLAT": None,
            "ZIP_CODE": "050000"
        },
        "CUST_ORDER_ITEMS": [{
            "EXTERNAL_ID": f"{external_id}-ITEM-1",
            "ORDER_NUM": 1,
            "PO_COMPONENT_ID": -1,
            "PRODUCT_OFFER_STRUCT_ID": 555,  # You need to specify the actual struct ID
            "PRODUCT_NUM": "ACC-001",  # You need to specify the actual product number
            "RESOURCE_SPEC_ID": 4444,  # You need to specify the actual resource spec ID
            "SERVICE_COUNT": 1,
            "PO_STRUCT_ELEMENTS": [{
                "PO_STRUCT_ELEMENT_ID": 777,  # You need to specify the actual element ID
                "ACTION_DATE": datetime.now().strftime("%Y-%m-%dT%H:%M:%S.000"),
                "SERVICE_COUNT": 1
            }]
        }]
    }

def create_work_order_payload(customer_account_id: int, order_id: Optional[int] = None) -> Dict[str, Any]:
    """Create a work order payload."""
    external_id = f"EXT-WO-{customer_account_id}-{int(datetime.now().timestamp())}"
    
    payload = {
        "filialId": 1,
        "customerAccountId": customer_account_id,
        "externalId": external_id,
        "productOfferId": 1234,
        "comments": "Technician visit needed",
        "address": {
            "streetId": 555,
            "houseNo": "12",
            "houseFraction": None,
            "flatNo": "45",
            "flatFraction": None,
            "zip": "050000"
        },
        "custOrderItem": {
            "externalId": f"{external_id}-ITEM-1",
            "actionId": 1,  # 1=install, 2=change, 3=disconnect
            "productOfferStructId": 9876,
            "productInstanceId": None,
            "productNum": "123",
            "resourceSpecId": None,
            "oneChargeElement": [2345324]
        },
        "installDate": "2025-10-20 10:00:00"
    }
    
    if order_id:
        payload["orderId"] = order_id
        
    return payload

# =============================================================================
# MAIN FUNCTIONS
# =============================================================================

def main():
    """Main function to create orders."""
    print("=" * 60)
    print("🏭 ORDER CREATION SCRIPT")
    print("=" * 60)
    print(f"👤 Customer Account ID: {CUSTOMER_ACCOUNT_ID}")
    print(f"🔑 API Key: {API_KEY[:10]}...")
    print(f"🌐 Base URL: {BASE_URL}")
    print("=" * 60)
    
    # Check database connection
    print("\n📊 Checking database...")
    user_info = get_user_info(CUSTOMER_ACCOUNT_ID)
    if user_info:
        print(f"✅ User found: {user_info}")
    else:
        print(f"⚠️  User {CUSTOMER_ACCOUNT_ID} not found in database")
        print("   Creating order with default values...")
    
    # Get available offers
    offers = get_offers()
    if offers:
        print(f"📦 Found {len(offers)} offers in database:")
        for offer in offers[:3]:  # Show first 3
            print(f"   - {offer['title']} (ID: {offer['id']})")
    else:
        print("⚠️  No offers found in database")
    
    # Setup session
    session = setup_session()
    
    # Create order
    print(f"\n🚀 Creating order for customer {CUSTOMER_ACCOUNT_ID}...")
    
    # Option 1: Create new order
    print("\n" + "=" * 40)
    print("📋 OPTION 1: CREATE NEW ORDER")
    print("=" * 40)
    
    order_payload = create_basic_order_payload(CUSTOMER_ACCOUNT_ID)
    result1 = create_new_order(session, order_payload)
    
    # Option 2: Create work order
    print("\n" + "=" * 40)
    print("🔧 OPTION 2: CREATE WORK ORDER")
    print("=" * 40)
    
    work_order_payload = create_work_order_payload(CUSTOMER_ACCOUNT_ID)
    result2 = create_work_order(session, work_order_payload)
    
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    print("✅ Script completed!")
    print(f"📋 New Order Result: {result1.get('DATA', {}).get('id', 'Failed')}")
    print(f"🔧 Work Order Result: {result2.get('DATA', {}).get('id', 'Failed')}")

def interactive_mode():
    """Interactive mode for creating custom orders."""
    print("=" * 60)
    print("🎯 INTERACTIVE ORDER CREATION")
    print("=" * 60)
    
    # Get user input
    customer_id = input(f"Enter Customer Account ID (default: {CUSTOMER_ACCOUNT_ID}): ").strip()
    if not customer_id:
        customer_id = CUSTOMER_ACCOUNT_ID
    else:
        customer_id = int(customer_id)
    
    print(f"\nCreating order for customer: {customer_id}")
    
    # Get order type
    order_type = input("Order type (1=New Order, 2=Work Order): ").strip()
    
    session = setup_session()
    
    if order_type == "1":
        payload = create_basic_order_payload(customer_id)
        result = create_new_order(session, payload)
    elif order_type == "2":
        payload = create_work_order_payload(customer_id)
        result = create_work_order(session, payload)
    else:
        print("❌ Invalid order type")
        return
    
    print(f"\n🎉 Order creation completed!")

# =============================================================================
# SCRIPT ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        interactive_mode()
    else:
        main()