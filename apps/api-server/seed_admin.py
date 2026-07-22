#!/usr/bin/env python
"""
Admin User Seeding CLI Tool for Paper Spells.
Generates secure PBKDF2-SHA256 password hashes matching the AdminRepository spec
and outputs copy-pasteable wrangler commands for local/production databases.
"""
from __future__ import annotations
import getpass
import hashlib
import os
import uuid
import sys

def hash_password(password: str) -> str:
    # Match the pbkdf2 settings in AdminRepository: 260,000 iterations, SHA-256
    salt = os.urandom(16).hex()
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260000)
    return f"{salt}${key.hex()}"

def main():
    print("=" * 60)
    print("🪄  Paper Spells — Admin User Seeding Utility")
    print("=" * 60)
    print("This script generates a secure hashed administrator account and formats")
    print("the SQL queries to seed your Cloudflare D1 database.")
    print()

    # Get credentials
    username = input("Enter admin username: ").strip()
    if not username:
        print("Error: Username cannot be empty.")
        sys.exit(1)

    password = getpass.getpass("Enter admin password: ")
    confirm = getpass.getpass("Confirm admin password: ")

    if password != confirm:
        print("Error: Passwords do not match.")
        sys.exit(1)

    if len(password) < 6:
        print("Warning: Password is short. We recommend at least 8 characters.")

    # Generate records
    admin_id = str(uuid.uuid4())
    pw_hash = hash_password(password)

    sql_statement = f"INSERT INTO admins (id, username, password_hash) VALUES ('{admin_id}', '{username}', '{pw_hash}');"

    print("\n" + "-" * 60)
    print("🔑  Generated SQL Insert Statement")
    print("-" * 60)
    print(sql_statement)
    print("-" * 60)

    print("\n🚀  Cloudflare Wrangler Deployment Commands")
    print("-" * 60)
    print("To seed your LOCAL wrangler development database, run:")
    print(f'npx wrangler d1 execute paper-spells-db --local --command "{sql_statement}"')
    print()
    print("To seed your PRODUCTION remote D1 database on Cloudflare, run:")
    print(f'npx wrangler d1 execute paper-spells-db --remote --command "{sql_statement}"')
    print("-" * 60)
    print()
    print("Enjoy bringing your doodles to life! 🪄")

if __name__ == "__main__":
    main()
