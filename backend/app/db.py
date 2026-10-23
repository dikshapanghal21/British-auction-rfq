
#
import logging
from pathlib import Path
import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo 
from psycopg.rows import dict_row 
from psycopg_pool import ConnectionPool 

log = logging.getLogger(__name__) #module logger
SCHEMA_FILE = Path(__file__).with_name("schema.sql") 
LOCK_ID = 724_001  #advisory lock so parallel workers don't race on CREATE TABLE.


def connect(url): #single connection
    conn = psycopg.connect(url, autocommit=True, row_factory=dict_row)
    conn.execute("SET TIME ZONE 'UTC'") #always the utc
    return conn


def create_pool(url): 
    def setup_conn(conn): #per connection?
        conn.execute("SET TIME ZONE 'UTC'") 

    return ConnectionPool(
        url,
        min_size=1, 
        max_size=10,
        kwargs={"autocommit": True, "row_factory": dict_row},
        configure=setup_conn,
        open=True, 
    )

def ensure_database(url): # create if missing
    dbname = conninfo_to_dict(url).get("dbname") # extract name
    if not dbname or dbname == "postgres": # skip default
        return
    try:
        with psycopg.connect(make_conninfo(url, dbname="postgres"), autocommit=True) as admin: # connect as the admin
            exists = admin.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,)).fetchone()
            if not exists:
                admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname))) 
                log.info("Created database %s", dbname) 
    except psycopg.Error as exc:
        log.warning("Could not auto-create database %s: %s", dbname, exc)

def apply_schema(conn): #run migrations!!
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (LOCK_ID,)) #grab the lock
        conn.execute(SCHEMA_FILE.read_text(encoding="utf-8")) #and apply sql!!
