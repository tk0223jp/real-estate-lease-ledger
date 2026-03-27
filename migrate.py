"""
既存データベースへのマイグレーションスクリプト。

実行方法:
    python migrate.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "instance", "rental.db")


def _add_column_if_missing(cur, table, col_def, existing_cols):
    col_name = col_def.split()[0]
    if col_name not in existing_cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col_def}")
        print(f"  {table}.{col_name}: 追加しました")
    else:
        print(f"  {table}.{col_name}: 既に存在します")


def migrate():
    if not os.path.exists(DB_PATH):
        print(f"DBが見つかりません: {DB_PATH}")
        print("run.py を起動すると自動作成されます。マイグレーション不要です。")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # ----------------------------------------------------------------
    # companies テーブル（フェーズ1）
    # ----------------------------------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            code       TEXT    NOT NULL UNIQUE,
            name       TEXT    NOT NULL,
            notes      TEXT,
            is_deleted INTEGER NOT NULL DEFAULT 0,
            created_at TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
    """)
    print("companies テーブル: OK")

    # ----------------------------------------------------------------
    # journal_patterns テーブル（フェーズ2）
    # ----------------------------------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS journal_patterns (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            name                TEXT    NOT NULL,
            debit_account_code  TEXT,
            debit_account_name  TEXT    NOT NULL DEFAULT '地代家賃',
            credit_account_code TEXT,
            credit_account_name TEXT    NOT NULL DEFAULT '普通預金',
            dept_code           TEXT,
            notes               TEXT,
            is_deleted          INTEGER NOT NULL DEFAULT 0,
            created_at          TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
            updated_at          TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
    """)
    print("journal_patterns テーブル: OK")

    # ----------------------------------------------------------------
    # properties に company_id / property_no 追加（フェーズ1）
    # ----------------------------------------------------------------
    cur.execute("PRAGMA table_info(properties)")
    prop_cols = {row[1] for row in cur.fetchall()}

    _add_column_if_missing(cur, "properties", "company_id INTEGER REFERENCES companies(id)", prop_cols)
    if "property_no" not in prop_cols:
        cur.execute("ALTER TABLE properties ADD COLUMN property_no TEXT")
        cur.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_property_no
            ON properties(property_no)
            WHERE property_no IS NOT NULL
        """)
        print("  properties.property_no: 追加しました")
    else:
        print("  properties.property_no: 既に存在します")

    # ----------------------------------------------------------------
    # contracts に解約フィールド + 仕訳パターンFK 追加（フェーズ2）
    # ----------------------------------------------------------------
    cur.execute("PRAGMA table_info(contracts)")
    con_cols = {row[1] for row in cur.fetchall()}

    # 解約フィールド
    _add_column_if_missing(cur, "contracts", "terminated_at TEXT", con_cols)
    _add_column_if_missing(cur, "contracts", "vacated_at TEXT", con_cols)
    _add_column_if_missing(cur, "contracts", "termination_reason TEXT", con_cols)

    # 仕訳パターンFK（費目ごと）
    _add_column_if_missing(
        cur, "contracts",
        "rent_journal_pattern_id INTEGER REFERENCES journal_patterns(id)",
        con_cols
    )
    _add_column_if_missing(
        cur, "contracts",
        "mgmt_fee_journal_pattern_id INTEGER REFERENCES journal_patterns(id)",
        con_cols
    )
    _add_column_if_missing(
        cur, "contracts",
        "parking_journal_pattern_id INTEGER REFERENCES journal_patterns(id)",
        con_cols
    )

    conn.commit()
    conn.close()
    print("\nマイグレーション完了！")


if __name__ == "__main__":
    migrate()
