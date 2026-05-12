#!/usr/bin/env python3
"""Migrate SQLite favorites.db to MySQL.

Usage:
    python scripts/migrate_sqlite_to_mysql.py [--sqlite PATH] [--mysql-host HOST]
"""

import argparse
import json
import sqlite3

import aiomysql
import pymysql


def migrate_sqlite_to_mysql(sqlite_path: str, mysql_config: dict) -> None:
    """Read SQLite DB and write all data to MySQL."""

    # --- Read SQLite ---
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # --- Connect MySQL ---
    mysql_conn = pymysql.connect(
        host=mysql_config["host"],
        port=mysql_config["port"],
        user=mysql_config["user"],
        password=mysql_config["password"],
        database=mysql_config["database"],
        charset="utf8mb4",
    )
    mcur = mysql_conn.cursor()

    try:
        # --- Create tables (skip if exist) ---
        print("Creating MySQL tables...")
        mcur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username VARCHAR(255),
                first_name VARCHAR(255),
                last_name VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        mcur.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                user_id BIGINT NOT NULL,
                actress_name VARCHAR(255) NOT NULL,
                actress_id VARCHAR(255),
                actress_data JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                UNIQUE KEY uk_user_actress (user_id, actress_name)
            )
        """)
        mcur.execute("""
            CREATE TABLE IF NOT EXISTS favorite_queries (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                user_id BIGINT NOT NULL,
                actress_name VARCHAR(255) NOT NULL,
                query_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        mcur.execute("""
            CREATE TABLE IF NOT EXISTS actress_works (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                actress_name VARCHAR(255) NOT NULL,
                av_id VARCHAR(255) NOT NULL,
                title VARCHAR(500),
                date VARCHAR(20),
                url VARCHAR(500),
                img TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uk_actress_av (actress_name, av_id)
            )
        """)
        mcur.execute("""
            CREATE TABLE IF NOT EXISTS user_push_settings (
                user_id BIGINT PRIMARY KEY,
                push_enabled BOOLEAN DEFAULT 1,
                last_check TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        mysql_conn.commit()
        print("MySQL tables ready.")

        # --- Migrate users ---
        print("\nMigrating users...")
        cur.execute("SELECT * FROM users")
        rows = cur.fetchall()
        for row in rows:
            mcur.execute(
                """
                INSERT IGNORE INTO users (user_id, username, first_name, last_name, created_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (row["user_id"], row["username"], row["first_name"], row["last_name"], row["created_at"]),
            )
        mysql_conn.commit()
        print(f"  Users: {len(rows)} rows")

        # --- Migrate favorites ---
        print("\nMigrating favorites...")
        cur.execute("SELECT * FROM favorites ORDER BY id")
        rows = cur.fetchall()
        for row in rows:
            actress_data = row["actress_data"]
            if actress_data and isinstance(actress_data, str):
                try:
                    json.loads(actress_data)  # validate JSON
                except json.JSONDecodeError:
                    actress_data = None
            mcur.execute(
                """
                INSERT IGNORE INTO favorites (id, user_id, actress_name, actress_id, actress_data, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (row["id"], row["user_id"], row["actress_name"], row["actress_id"], actress_data, row["created_at"]),
            )
        mysql_conn.commit()
        print(f"  Favorites: {len(rows)} rows")

        # --- Migrate favorite_queries ---
        print("\nMigrating favorite_queries...")
        cur.execute("SELECT * FROM favorite_queries ORDER BY id")
        rows = cur.fetchall()
        for row in rows:
            mcur.execute(
                """
                INSERT IGNORE INTO favorite_queries (id, user_id, actress_name, query_time)
                VALUES (%s, %s, %s, %s)
                """,
                (row["id"], row["user_id"], row["actress_name"], row["query_time"]),
            )
        mysql_conn.commit()
        print(f"  Favorite queries: {len(rows)} rows")

        # --- Migrate actress_works ---
        print("\nMigrating actress_works...")
        cur.execute("SELECT * FROM actress_works ORDER BY id")
        rows = cur.fetchall()
        for row in rows:
            mcur.execute(
                """
                INSERT IGNORE INTO actress_works (id, actress_name, av_id, title, date, url, img, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (row["id"], row["actress_name"], row["av_id"], row["title"], row["date"], row["url"], row["img"], row["created_at"]),
            )
        mysql_conn.commit()
        print(f"  Actress works: {len(rows)} rows")

        # --- Migrate user_push_settings ---
        print("\nMigrating user_push_settings...")
        cur.execute("SELECT * FROM user_push_settings")
        rows = cur.fetchall()
        for row in rows:
            mcur.execute(
                """
                INSERT IGNORE INTO user_push_settings (user_id, push_enabled, last_check)
                VALUES (%s, %s, %s)
                """,
                (row["user_id"], row["push_enabled"], row["last_check"]),
            )
        mysql_conn.commit()
        print(f"  Push settings: {len(rows)} rows")

        print("\n✅ Migration complete!")

    except Exception as e:
        mysql_conn.rollback()
        print(f"\n❌ Migration failed: {e}")
        raise
    finally:
        conn.close()
        mysql_conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate SQLite favorites.db to MySQL")
    parser.add_argument("--sqlite", default="data/favorites.db", help="Path to SQLite DB")
    parser.add_argument("--mysql-host", default="127.0.0.1")
    parser.add_argument("--mysql-port", type=int, default=3306)
    parser.add_argument("--mysql-user", default="javbot")
    parser.add_argument("--mysql-password", default="javbot")
    parser.add_argument("--mysql-database", default="javbot")
    args = parser.parse_args()

    migrate_sqlite_to_mysql(args.sqlite, {
        "host": args.mysql_host,
        "port": args.mysql_port,
        "user": args.mysql_user,
        "password": args.mysql_password,
        "database": args.mysql_database,
    })
