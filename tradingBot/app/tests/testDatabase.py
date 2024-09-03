import pytest
from database import get_db_connection, init_db

def test_db_connection():
    conn = get_db_connection()
    assert conn is not None
    conn.close()

def test_init_db():
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='trades');")
        assert cursor.fetchone()[0] == True
    conn.close()
