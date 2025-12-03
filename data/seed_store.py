import os
import sqlite3
from datetime import datetime, timedelta


def main() -> None:
    os.makedirs("data", exist_ok=True)
    db_path = "data/store.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.executescript(
        """
        DROP TABLE IF EXISTS order_items;
        DROP TABLE IF EXISTS orders;
        DROP TABLE IF EXISTS products;
        DROP TABLE IF EXISTS customers;

        CREATE TABLE customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            address TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            stock_level INTEGER NOT NULL
        );

        CREATE TABLE orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            order_date TEXT NOT NULL,
            total_amount REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL,
            FOREIGN KEY(customer_id) REFERENCES customers(id)
        );

        CREATE TABLE order_items (
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            FOREIGN KEY(order_id) REFERENCES orders(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        );
        """
    )

    now = datetime.utcnow()
    customers = [
        ("Alice Smith", "alice@example.com", "555-123-0001", "123 Main St, Springfield", now - timedelta(days=300)),
        ("Bob Johnson", "bob.j@example.com", "555-123-0002", "456 Oak Ave, Metropolis", now - timedelta(days=200)),
        ("Charlie Brown", "charlie.brown@example.com", "555-123-0003", "789 Pine Rd, Smallville", now - timedelta(days=150)),
        ("Dana Lee", "dana.lee@example.com", "555-123-0004", "321 Birch Blvd, Gotham", now - timedelta(days=90)),
        ("Evan Wright", "evan.w@example.com", "555-123-0005", "654 Cedar St, Star City", now - timedelta(days=30)),
    ]
    cur.executemany(
        "INSERT INTO customers(name,email,phone,address,created_at) VALUES (?,?,?,?,?)",
        [(n, e, p, a, dt.date().isoformat()) for n, e, p, a, dt in customers],
    )

    products = [
        ("T-shirt", "Apparel", 25.00, 200),
        ("Jeans", "Apparel", 60.00, 120),
        ("Sneakers", "Footwear", 90.00, 80),
        ("Backpack", "Accessories", 45.00, 50),
        ("Water Bottle", "Accessories", 15.00, 300),
    ]
    cur.executemany(
        "INSERT INTO products(name, category, price, stock_level) VALUES (?,?,?,?)",
        products,
    )

    orders = [
        (1, now - timedelta(days=40), "shipped"),
        (1, now - timedelta(days=10), "processing"),
        (2, now - timedelta(days=70), "delivered"),
        (3, now - timedelta(days=15), "shipped"),
        (4, now - timedelta(days=5), "processing"),
        (5, now - timedelta(days=2), "pending"),
    ]
    cur.executemany(
        "INSERT INTO orders(customer_id, order_date, total_amount, status) VALUES (?,?,0,?)",
        [(cid, dt.date().isoformat(), status) for cid, dt, status in orders],
    )

    order_items = [
        # order 1
        (1, 1, 2, 25.00),  # T-shirt x2
        (1, 5, 3, 15.00),  # Water Bottle x3
        # order 2
        (2, 2, 1, 60.00),  # Jeans x1
        (2, 3, 1, 90.00),  # Sneakers x1
        # order 3
        (3, 1, 1, 25.00),
        (3, 2, 2, 60.00),
        # order 4
        (4, 4, 1, 45.00),
        (4, 5, 2, 15.00),
        # order 5
        (5, 1, 3, 25.00),
        (5, 3, 1, 90.00),
        # order 6
        (6, 2, 1, 60.00),
        (6, 4, 1, 45.00),
    ]
    cur.executemany(
        "INSERT INTO order_items(order_id, product_id, quantity, unit_price) VALUES (?,?,?,?)",
        order_items,
    )

    # Recompute totals based on order_items
    cur.execute(
        """
        UPDATE orders
        SET total_amount = (
            SELECT SUM(quantity * unit_price) FROM order_items WHERE order_items.order_id = orders.id
        )
        """
    )

    conn.commit()
    conn.close()
    print(f"Database seeded at {db_path}")


if __name__ == "__main__":
    main()
