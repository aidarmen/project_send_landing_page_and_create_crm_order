#!/usr/bin/env python3
"""
Script to migrate currency from 'KZT' to '₸' in existing offers.
Run this once to update existing database records.
"""
import os
from dotenv import load_dotenv
from db import db

load_dotenv()

def migrate_currency():
    """Update all offers with currency 'KZT' to '₸'"""
    with db() as conn:
        c = conn.cursor()
        
        # Count how many records need updating
        c.execute("SELECT COUNT(*) FROM offers WHERE currency = 'KZT'")
        count = c.fetchone()[0]
        
        if count == 0:
            print("No records with 'KZT' currency found. Nothing to migrate.")
            return
        
        print(f"Found {count} offer(s) with 'KZT' currency. Updating to '₸'...")
        
        # Update all records
        c.execute("UPDATE offers SET currency = '₸' WHERE currency = 'KZT'")
        conn.commit()
        
        print(f"Successfully updated {count} record(s).")
        
        # Verify
        c.execute("SELECT COUNT(*) FROM offers WHERE currency = 'KZT'")
        remaining = c.fetchone()[0]
        if remaining == 0:
            print("Migration completed successfully!")
        else:
            print(f"Warning: {remaining} record(s) still have 'KZT' currency.")

if __name__ == "__main__":
    migrate_currency()

