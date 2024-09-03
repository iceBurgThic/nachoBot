import psycopg2
from configparser import ConfigParser

# Load database configuration from serverAppConfig or .env
config = ConfigParser()
config.read('serverAppConfig')

DB_HOST = config.get('database', 'HOST', fallback='localhost')
DB_PORT = config.get('database', 'PORT', fallback='5432')
DB_NAME = config.get('database', 'NAME', fallback='trading_app')
DB_USER = config.get('database', 'USER', fallback='postgres')
DB_PASSWORD = config.get('database', 'PASSWORD', fallback='password')

def get_db_connection():
    """Establish a new database connection to TimescaleDB."""
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def init_db():
    """Initialize the database schema with TimescaleDB hypertables."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    id SERIAL PRIMARY KEY,
                    asset VARCHAR(50) NOT NULL,
                    trade_type VARCHAR(10) NOT NULL,
                    trade_amount FLOAT NOT NULL,
                    price FLOAT NOT NULL,
                    stop_loss FLOAT NOT NULL,
                    timestamp TIMESTAMPTZ DEFAULT NOW()
                )
            ''')
            cursor.execute('''
                SELECT create_hypertable('trades', 'timestamp', if_not_exists => TRUE);
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS errors (
                    id SERIAL PRIMARY KEY,
                    error_message TEXT NOT NULL,
                    severity VARCHAR(10),
                    timestamp TIMESTAMPTZ DEFAULT NOW()
                )
            ''')
            cursor.execute('''
                SELECT create_hypertable('errors', 'timestamp', if_not_exists => TRUE);
            ''')
            conn.commit()

init_db()
