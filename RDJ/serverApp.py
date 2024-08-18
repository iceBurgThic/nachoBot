import os
import time
import threading
from datetime import datetime, timedelta
from functools import wraps

import jwt
import requests
import logging
import psycopg2
from configparser import ConfigParser
from flask import Flask, request, jsonify, g
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from retrying import retry

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask app initialization
app = Flask(__name__)

# Configure Flask Limiter for rate limiting
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"]
)

# Load configuration from a file
config = ConfigParser()
config.read('config.ini')

# JWT Secret Key and Algorithm
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', config.get('security', 'secret_key', fallback='your-secret-key'))
JWT_ALGORITHM = 'HS256'

# Database connection settings
DB_HOST = config.get('database', 'host', fallback='localhost')
DB_PORT = config.get('database', 'port', fallback='5432')
DB_NAME = config.get('database', 'name', fallback='trading_app')
DB_USER = config.get('database', 'user', fallback='postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', config.get('database', 'password', fallback='password'))

# Trade settings
STOP_LOSS_PERCENTAGE = config.getfloat('trading', 'STOP_LOSS_PERCENTAGE', fallback=0.02)
COOLDOWN_PERIOD_MINUTES = config.getint('trading', 'COOLDOWN_PERIOD_MINUTES', fallback=5)
MAX_SIGNAL_AGE_SECONDS = config.getint('trading', 'MAX_SIGNAL_AGE_SECONDS', fallback=60)
AVAILABLE_CAPITAL = float(os.getenv('AVAILABLE_CAPITAL', config.getfloat('trading', 'available_capital', fallback=10000)))

# Thread-safe lock for database access
db_lock = threading.Lock()

# Initialize the last signal time tracking
last_signal_time = {}

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
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id SERIAL PRIMARY KEY,
                    asset VARCHAR(50),
                    trade_type VARCHAR(10),
                    trade_amount FLOAT,
                    price FLOAT,
                    stop_loss FLOAT,
                    timestamp TIMESTAMPTZ DEFAULT NOW()
                );
            """)
            cursor.execute("""
                SELECT create_hypertable('trades', 'timestamp', if_not_exists => TRUE);
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS errors (
                    id SERIAL PRIMARY KEY,
                    error_message TEXT,
                    severity VARCHAR(10),
                    timestamp TIMESTAMPTZ DEFAULT NOW()
                );
            """)
            cursor.execute("""
                SELECT create_hypertable('errors', 'timestamp', if_not_exists => TRUE);
            """)
            conn.commit()

# JWT Authentication decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            log_error("Missing API token.", severity='WARNING')
            return jsonify({"status": "error", "message": "Token is missing!"}), 403
        try:
            jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        except jwt.ExpiredSignatureError:
            log_error("Expired API token.", severity='WARNING')
            return jsonify({"status": "error", "message": "Token has expired!"}), 403
        except jwt.InvalidTokenError:
            log_error("Invalid API token.", severity='WARNING')
            return jsonify({"status": "error", "message": "Token is invalid!"}), 403
        return f(*args, **kwargs)
    return decorated

def log_trade(asset, trade_type, trade_amount, price, stop_loss):
    """Log trade details into the database."""
    with db_lock:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO trades (asset, trade_type, trade_amount, price, stop_loss, timestamp)
                    VALUES (%s, %s, %s, %s, %s, NOW())
                """, (asset, trade_type, trade_amount, price, stop_loss))
                conn.commit()

def log_error(error_message, severity='ERROR'):
    """Log errors into the database."""
    with db_lock:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO errors (error_message, severity, timestamp)
                    VALUES (%s, %s, NOW())
                """, (error_message, severity))
                conn.commit()

@retry(stop_max_attempt_number=3, wait_fixed=2000)
def get_live_price(asset):
    """Fetch the live price of an asset from the external API."""
    try:
        response = requests.get(f"https://api.example.com/price/{asset}")
        response.raise_for_status()
        data = response.json()
        return data['price']
    except requests.exceptions.RequestException as e:
        log_error(f"Error fetching live price for {asset}: {e}", severity='CRITICAL')
        return None

@retry(stop_max_attempt_number=3, wait_fixed=2000)
def get_account_balance():
    """Fetch the current account balance from the external API."""
    try:
        response = requests.get("https://api.example.com/account/balance")
        response.raise_for_status()
        data = response.json()
        return data['balance']
    except requests.exceptions.RequestException as e:
        log_error(f"Error fetching account balance: {e}", severity='CRITICAL')
        return AVAILABLE_CAPITAL  # Default to known available capital if error occurs

def calculate_trade_amount(signal):
    """Calculate the amount to trade based on available capital."""
    available_capital = get_account_balance()
    
    if available_capital is None:
        log_error("Could not retrieve account balance, defaulting to known available capital.", severity='WARNING')
        available_capital = AVAILABLE_CAPITAL
    
    # Trade 10% of available capital
    trade_amount = available_capital * 0.1
    return trade_amount

def execute_trade(signal):
    """Execute a trade based on the received signal."""
    asset = signal['asset']
    trade_amount = calculate_trade_amount(signal)
    live_price = get_live_price(asset)
    
    if live_price is None:
        log_error(f"Could not execute trade for {asset} due to missing live price.", severity='CRITICAL')
        return

    stop_loss_price = live_price * (1 - STOP_LOSS_PERCENTAGE)
    
    log_trade(asset, signal['type'], trade_amount, live_price, stop_loss_price)

    # Placeholder for actual trade execution logic with the brokerage API
    print(f"Executing {signal['type']} trade for {asset} with amount {trade_amount} at price {live_price}.")
    print(f"Setting stop-loss at {stop_loss_price}.")

def process_signal(signal):
    """Process the incoming trade signal."""
    asset = signal['asset']
    signal_type = signal['type']  # 'buy' or 'sell'
    
    current_time = datetime.now()
    signal_time = datetime.fromtimestamp(signal['timestamp'])

    if (current_time - signal_time).seconds > MAX_SIGNAL_AGE_SECONDS:
        log_error(f"Ignoring old signal for {asset}. Signal age: {current_time - signal_time} seconds.", severity='INFO')
        return

    if asset in last_signal_time:
        last_time, last_type = last_signal_time[asset]
        if signal_type == last_type and current_time - last_time < timedelta(minutes=COOLDOWN_PERIOD_MINUTES):
            log_error(f"Ignoring {signal_type} signal for {asset} due to cooldown.", severity='INFO')
            return

    last_signal_time[asset] = (current_time, signal_type)
    execute_trade(signal)

@app.route('/signal', methods=['POST'])
@limiter.limit("10 per minute")
@token_required
def receive_signal():
    """API endpoint to receive and process trade signals."""
    signal = request.json
    if signal and 'asset' in signal and 'type' in signal and 'timestamp' in signal:
        process_signal(signal)
        return jsonify({"status": "success", "message": "Signal processed."}), 200
    else:
        log_error("Received invalid signal data.", severity='WARNING')
        return jsonify({"status": "error", "message": "Invalid signal data."}), 400

if __name__ == '__main__':
    init_db()  # Initialize the database schema
    app.run(debug=True)
