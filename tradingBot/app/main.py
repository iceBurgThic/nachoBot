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
from dotenv import load_dotenv
import hashlib
import hmac
import base64

# Load environment variables from .env file if present
load_dotenv()

# Setup logging
config = ConfigParser()
config.read('config.ini')
log_level = config.get('logging', 'LOG_LEVEL', fallback='INFO')
logging.basicConfig(level=getattr(logging, log_level.upper()))
logger = logging.getLogger(__name__)

# Flask app initialization
app = Flask(__name__)

# Configure Flask Limiter for rate limiting
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"]
)

# JWT Secret Key and Algorithm
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', config.get('security', 'JWT_SECRET_KEY', fallback='your-secret-key'))
JWT_ALGORITHM = config.get('security', 'JWT_ALGORITHM', fallback='HS256')

# Kraken API credentials
API_KEY = os.getenv('KRAKEN_API_KEY', config.get('kraken', 'API_KEY', fallback='your-api-key'))
API_SECRET = os.getenv('KRAKEN_API_SECRET', config.get('kraken', 'API_SECRET', fallback='your-api-secret'))

# Database connection settings
DB_HOST = config.get('database', 'HOST', fallback='localhost')
DB_PORT = config.get('database', 'PORT', fallback='5432')
DB_NAME = config.get('database', 'NAME', fallback='trading_app')
DB_USER = config.get('database', 'USER', fallback='postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', config.get('database', 'PASSWORD', fallback='password'))

# Trade settings
STOP_LOSS_PERCENTAGE = config.getfloat('trading', 'STOP_LOSS_PERCENTAGE', fallback=0.02)
COOLDOWN_PERIOD_MINUTES = config.getint('trading', 'COOLDOWN_PERIOD_MINUTES', fallback=5)
MAX_SIGNAL_AGE_SECONDS = config.getint('trading', 'MAX_SIGNAL_AGE_SECONDS', fallback=60)
AVAILABLE_CAPITAL = float(os.getenv('AVAILABLE_CAPITAL', config.getfloat('trading', 'AVAILABLE_CAPITAL', fallback=10000)))

# SSL Certificate paths
SSL_CERT_PATH = config.get('security', 'SSL_CERT_PATH', fallback='/etc/ssl/certs/fullchain.pem')
SSL_KEY_PATH = config.get('security', 'SSL_KEY_PATH', fallback='/etc/ssl/private/privkey.pem')

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
    def token_required_func(*args, **kwargs):
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
    return token_required_func

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

def kraken_request(uri_path, data):
    """Make a signed request to the Kraken API."""
    url = f"https://api.kraken.com{uri_path}"
    data['nonce'] = str(int(time.time() * 1000))
    post_data = urllib.parse.urlencode(data)
    message = data['nonce'] + post_data
    message = uri_path.encode('utf-8') + hashlib.sha256(message.encode('utf-8')).digest()
    signature = hmac.new(base64.b64decode(API_SECRET), message, hashlib.sha512)
    headers = {
        'API-Key': API_KEY,
        'API-Sign': base64.b64encode(signature.digest()),
    }
    response = requests.post(url, headers=headers, data=post_data)
    return response.json()

@retry(stop_max_attempt_number=3, wait_fixed=2000)
def get_live_price(asset):
    """Fetch the live price of an asset from the Kraken API."""
    pair = asset.upper() + "USD"
    response = kraken_request('/0/public/Ticker', {'pair': pair})
    if response.get('error'):
        log_error(f"Error fetching live price for {asset}: {response['error']}", severity='CRITICAL')
        return None
    price = float(response['result'][pair]['c'][0])
    return price

@retry(stop_max_attempt_number=3, wait_fixed=2000)
def get_account_balance():
    """Fetch the current account balance from the Kraken API."""
    response = kraken_request('/0/private/Balance', {})
    if response.get('error'):
        log_error(f"Error fetching account balance: {response['error']}", severity='CRITICAL')
        return AVAILABLE_CAPITAL  # Default to known available capital if error occurs
    balance = float(response['result'].get('ZUSD', AVAILABLE_CAPITAL))  # Adjust to your preferred base currency
    return balance

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

    # Placeholder for actual trade execution logic with the Kraken API
    order_type = "buy" if signal['type'] == "buy" else "sell"
    kraken_request('/0/private/AddOrder', {
        'pair': asset.upper() + "USD",
        'type': order_type,
        'ordertype': 'market',
        'volume': trade_amount,
        'validate': True  # Set to False to actually place the order
    })

    print(f"Executing {signal['type']} trade for {asset} with amount {trade_amount} at price {live_price}.")
    print(f"Setting stop-loss at {stop_loss_price}.")

def process_signal(signal):
    """Process the incoming trade signal."""
    asset = signal['asset']
    signal
