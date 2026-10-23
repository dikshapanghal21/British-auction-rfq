##.

import os
from pathlib import Path

from dotenv import load_dotenv #env loader.
from psycopg.conninfo import make_conninfo #build connstring?

load_dotenv(Path(__file__).resolve().parent.parent / ".env") #load .env
_base = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/british_auction") #fallback url
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL") or make_conninfo(_base, dbname="british_auction_test") #test db
os.environ["DATABASE_URL"] = TEST_DATABASE_URL #override 
os.environ["SWEEPER_ENABLED"] = "0" #no sweeper

import pytest  #noqa: E402

from app.db import apply_schema, connect, ensure_database  #noqa: E402

TABLES = "activity_logs, bids, suppliers, rfqs" #truncate the order


@pytest.fixture(scope="session", autouse=True)
def _schema(): #once per session
    ensure_database(TEST_DATABASE_URL) #create if is missing
    with connect(TEST_DATABASE_URL) as conn:
        apply_schema(conn) #run migrations


@pytest.fixture
def conn(): # resh connect
    with connect(TEST_DATABASE_URL) as c:
        c.execute(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE") #/
        yield c #


@pytest.fixture
def client(conn): #test the client!!
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c 
