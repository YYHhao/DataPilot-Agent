from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg

TABLES = {
    "customers": (
        "olist_customers_dataset.csv",
        """customer_id text, customer_unique_id text, customer_zip_code_prefix integer,
        customer_city text, customer_state text""",
    ),
    "geolocation": (
        "olist_geolocation_dataset.csv",
        """geolocation_zip_code_prefix integer, geolocation_lat double precision,
        geolocation_lng double precision, geolocation_city text, geolocation_state text""",
    ),
    "orders": (
        "olist_orders_dataset.csv",
        """order_id text, customer_id text, order_status text,
        order_purchase_timestamp timestamp, order_approved_at timestamp,
        order_delivered_carrier_date timestamp, order_delivered_customer_date timestamp,
        order_estimated_delivery_date timestamp""",
    ),
    "order_items": (
        "olist_order_items_dataset.csv",
        """order_id text, order_item_id integer, product_id text, seller_id text,
        shipping_limit_date timestamp, price numeric(12,2), freight_value numeric(12,2)""",
    ),
    "order_payments": (
        "olist_order_payments_dataset.csv",
        """order_id text, payment_sequential integer, payment_type text,
        payment_installments integer, payment_value numeric(12,2)""",
    ),
    "order_reviews": (
        "olist_order_reviews_dataset.csv",
        """review_id text, order_id text, review_score integer, review_comment_title text,
        review_comment_message text, review_creation_date timestamp,
        review_answer_timestamp timestamp""",
    ),
    "products": (
        "olist_products_dataset.csv",
        """product_id text, product_category_name text, product_name_lenght integer,
        product_description_lenght integer, product_photos_qty integer,
        product_weight_g numeric, product_length_cm numeric, product_height_cm numeric,
        product_width_cm numeric""",
    ),
    "sellers": (
        "olist_sellers_dataset.csv",
        """seller_id text, seller_zip_code_prefix integer, seller_city text,
        seller_state text""",
    ),
    "product_category_translation": (
        "product_category_name_translation.csv",
        "product_category_name text, product_category_name_english text",
    ),
}

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id)",
    "CREATE INDEX IF NOT EXISTS idx_orders_purchase ON orders(order_purchase_timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_items_order ON order_items(order_id)",
    "CREATE INDEX IF NOT EXISTS idx_items_product ON order_items(product_id)",
    "CREATE INDEX IF NOT EXISTS idx_items_seller ON order_items(seller_id)",
    "CREATE INDEX IF NOT EXISTS idx_payments_order ON order_payments(order_id)",
    "CREATE INDEX IF NOT EXISTS idx_reviews_order ON order_reviews(order_id)",
    "CREATE INDEX IF NOT EXISTS idx_products_category ON products(product_category_name)",
    "CREATE INDEX IF NOT EXISTS idx_geo_zip ON geolocation(geolocation_zip_code_prefix)",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="将 Olist CSV 导入 PostgreSQL")
    parser.add_argument("--csv-dir", type=Path, default=Path("data/olist_csv"))
    parser.add_argument("--replace", action="store_true", help="删除并重新导入已有表")
    args = parser.parse_args()

    dsn = os.getenv("OLIST_ADMIN_DATABASE_URL")
    if not dsn:
        raise SystemExit("请先设置环境变量 OLIST_ADMIN_DATABASE_URL")

    missing = [
        filename for filename, _ in TABLES.values() if not (args.csv_dir / filename).is_file()
    ]
    if missing:
        raise SystemExit(f"缺少 CSV 文件：{', '.join(missing)}")

    with psycopg.connect(dsn) as connection, connection.cursor() as cursor:
        for table, (filename, columns) in TABLES.items():
            exists = cursor.execute("SELECT to_regclass(%s)", (f"public.{table}",)).fetchone()[0]
            if exists and not args.replace:
                raise SystemExit(f"表 {table} 已存在；如需重新导入，请增加 --replace")
            if exists:
                cursor.execute(f'DROP TABLE "{table}"')
            cursor.execute(f'CREATE TABLE "{table}" ({columns})')
            path = args.csv_dir / filename
            print(f"正在导入 {filename} -> {table} ...")
            with (
                path.open("r", encoding="utf-8", newline="") as source,
                cursor.copy(
                    f"COPY \"{table}\" FROM STDIN WITH (FORMAT CSV, HEADER TRUE, NULL '')"
                ) as copy,
            ):
                while chunk := source.read(1024 * 1024):
                    copy.write(chunk)

        for statement in INDEXES:
            cursor.execute(statement)

        cursor.execute("ANALYZE")
        for table in TABLES:
            count = cursor.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            print(f"{table}: {count:,} 行")

    print("Olist 数据导入完成。")


if __name__ == "__main__":
    main()
