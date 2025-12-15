
import random
import string
from datetime import datetime, timedelta

import MySQLdb
from faker import Faker

from config import TestConfig


def get_db_connection():
    return MySQLdb.connect(
        host=TestConfig.MYSQL_HOST,
        user=TestConfig.MYSQL_USER,
        password=TestConfig.MYSQL_PASSWORD,
        db=TestConfig.MYSQL_DB,
        cursorclass=MySQLdb.cursors.DictCursor,
    )


def create_tables(cursor):
    # 1. Drop existing tables/views to start fresh
    cursor.execute("DROP VIEW IF EXISTS expenses_denorm")
    cursor.execute("DROP TABLE IF EXISTS expense_fact_tags")  # Drop junction table first
    cursor.execute("DROP TABLE IF EXISTS expenses_fact")
    cursor.execute("DROP TABLE IF EXISTS expense_categories")
    cursor.execute("DROP TABLE IF EXISTS vendors")
    cursor.execute("DROP TABLE IF EXISTS payment_methods")
    cursor.execute("DROP TABLE IF EXISTS expense_tags")

    # 2. Create Dimension Tables
    # Categories
    cursor.execute(
        """
        CREATE TABLE expense_categories (
            category_id INT AUTO_INCREMENT PRIMARY KEY,
            category_name VARCHAR(50) NOT NULL UNIQUE,
            description VARCHAR(255)
        )
    """
    )

    # Vendors
    cursor.execute(
        """
        CREATE TABLE vendors (
            vendor_id INT AUTO_INCREMENT PRIMARY KEY,
            vendor_name VARCHAR(100) NOT NULL UNIQUE,
            contact_info VARCHAR(255)
        )
    """
    )

    # Payment Methods
    cursor.execute(
        """
        CREATE TABLE payment_methods (
            payment_method_id INT AUTO_INCREMENT PRIMARY KEY,
            method_name VARCHAR(50) NOT NULL UNIQUE
        )
    """
    )

    # Tags (Optional dimension for many-to-many, but keeping it simple for now as a direct lookup or just unused in this iteration if not strictly required by the prompt's core logic, but let's add it for completeness)
    cursor.execute(
        """
        CREATE TABLE expense_tags (
            tag_id INT AUTO_INCREMENT PRIMARY KEY,
            tag_name VARCHAR(50) NOT NULL UNIQUE
        )
    """
    )

    # 3. Create Fact Table
    cursor.execute(
        """
        CREATE TABLE expenses_fact (
            expense_id INT AUTO_INCREMENT PRIMARY KEY,
            expense_date DATE NOT NULL,
            amount DECIMAL(10, 2) NOT NULL,
            category_id INT,
            vendor_id INT,
            payment_method_id INT,
            description TEXT,
            qty INT DEFAULT 1,
            unit_price DECIMAL(10, 2),
            FOREIGN KEY (category_id) REFERENCES expense_categories(category_id),
            FOREIGN KEY (vendor_id) REFERENCES vendors(vendor_id),
            FOREIGN KEY (payment_method_id) REFERENCES payment_methods(payment_method_id)
        )
    """
    )

    # 4. Create Denormalized View (for easier querying)
    cursor.execute(
        """
        CREATE VIEW expenses_denorm AS
        SELECT 
            e.expense_id,
            e.expense_date,
            e.amount,
            e.description,
            e.qty,
            e.unit_price,
            c.category_name,
            v.vendor_name,
            p.method_name as payment_method_name
        FROM expenses_fact e
        LEFT JOIN expense_categories c ON e.category_id = c.category_id
        LEFT JOIN vendors v ON e.vendor_id = v.vendor_id
        LEFT JOIN payment_methods p ON e.payment_method_id = p.payment_method_id
    """
    )


def seed_data(cursor, num_expenses=20):
    fake = Faker()

    # Seed Categories
    categories = ["Food", "Transportation", "Utilities", "Entertainment", "Healthcare", "Shopping", "Rent", "Education"]
    for cat in categories:
        cursor.execute(
            "INSERT IGNORE INTO expense_categories (category_name, description) VALUES (%s, %s)",
            (cat, fake.sentence()),
        )

    # Seed Vendors
    vendors = [
        "Jollibee",
        "McDonalds",
        "Starbucks",
        "Grab",
        "Meralco",
        "Maynilad",
        "Netflix",
        "Mercury Drug",
        "SM Store",
        "Landlord",
    ]
    for vendor in vendors:
        cursor.execute(
            "INSERT IGNORE INTO vendors (vendor_name, contact_info) VALUES (%s, %s)", (vendor, fake.phone_number())
        )

    # Seed Payment Methods
    methods = ["Cash", "Credit Card", "Debit Card", "GCash", "Maya", "Bank Transfer"]
    for method in methods:
        cursor.execute("INSERT IGNORE INTO payment_methods (method_name) VALUES (%s)", (method,))

    # Get IDs for seeding facts
    cursor.execute("SELECT category_id FROM expense_categories")
    cat_ids = [row["category_id"] for row in cursor.fetchall()]

    cursor.execute("SELECT vendor_id FROM vendors")
    vendor_ids = [row["vendor_id"] for row in cursor.fetchall()]

    cursor.execute("SELECT payment_method_id FROM payment_methods")
    method_ids = [row["payment_method_id"] for row in cursor.fetchall()]

    # Seed Expenses Fact
    for _ in range(num_expenses):
        date = fake.date_between(start_date="-1y", end_date="today")
        amount = round(random.uniform(50.0, 5000.0), 2)
        desc = fake.sentence()
        qty = random.randint(1, 5)
        unit_price = round(amount / qty, 2)

        cursor.execute(
            """
            INSERT INTO expenses_fact 
            (expense_date, amount, category_id, vendor_id, payment_method_id, description, qty, unit_price)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
            (
                date,
                amount,
                random.choice(cat_ids),
                random.choice(vendor_ids),
                random.choice(method_ids),
                desc,
                qty,
                unit_price,
            ),
        )


def ensure_schema_and_seed(num_expenses=20):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            create_tables(cursor)
            seed_data(cursor, num_expenses)
        conn.commit()
        print("Schema created and data seeded successfully.")
    finally:
        conn.close()


if __name__ == "__main__":
    ensure_schema_and_seed()
