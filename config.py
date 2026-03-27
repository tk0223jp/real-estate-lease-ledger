import os
from decimal import Decimal
from sqlalchemy import event
from sqlalchemy.engine import Engine

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "instance", "rental.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 消費税率
    CONSUMPTION_TAX_RATE = Decimal("0.10")

    # 契約書AI読み取り（Anthropic API）
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()
