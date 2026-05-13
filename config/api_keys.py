# 🔐 API KEYS AND CREDENTIALS
# ⚠️  NEVER COMMIT THIS FILE TO VERSION CONTROL
# ⚠️  This file is in .gitignore for security reasons

import os
from typing import Dict, Optional

class APIKeys:
    """
    Centralized API key management for Market Montrezor System
    Add your API keys here - they will be imported where needed
    """

    # ==================== YOUTUBE ====================
    YOUTUBE_API_KEY: Optional[str] = "AIzaSyAEw3uga2uUZ85-C7igQy5B3cHWr7vNV40"  # Free API, no key needed

    # ==================== YAHOO FINANCE ====================
    YAHOO_FINANCE_API_KEY: Optional[str] = None  # Free API, no key needed

    # ================= BINANCE ====================
    BINANCE_API_KEY: Optional[str] = None
    BINANCE_SECRET_KEY: Optional[str] = None
    BINANCE_TESTNET_API_KEY: Optional[str] = None
    BINANCE_TESTNET_SECRET_KEY: Optional[str] = None

    # ================= GLASSNODE ====================
    GLASSNODE_API_KEY: Optional[str] = None

    # ================= COINGECKO ====================
    COINGECKO_API_KEY: Optional[str] = "CG-f6FU1HLrUvViUUC2ZQZgN8dw"  # Free tier available

    # ================= CRYPTOCOMPARE ====================
    CRYPTOCOMPARE_API_KEY: Optional[str] = None

    # ================= ALPHA VANTAGE ====================
    ALPHA_VANTAGE_API_KEY: Optional[str] = None

    # ================= FINNHUB ====================
    FINNHUB_API_KEY: Optional[str] = None

    # ================= POLYGON ====================
    POLYGON_API_KEY: Optional[str] = None

    # ================= IEX CLOUD ====================
    IEX_CLOUD_API_KEY: Optional[str] = None

    # ================= DATABASE ====================
    DATABASE_URL: Optional[str] = None
    POSTGRES_USER: Optional[str] = None
    POSTGRES_PASSWORD: Optional[str] = None
    POSTGRES_HOST: Optional[str] = None
    POSTGRES_PORT: Optional[str] = None
    POSTGRES_DB: Optional[str] = None

    # ================= REDIS ====================
    REDIS_URL: Optional[str] = None
    REDIS_HOST: Optional[str] = None
    REDIS_PORT: Optional[str] = None
    REDIS_PASSWORD: Optional[str] = None

    # ================= TELEGRAM (for notifications) ====================
    TELEGRAM_API_ID: Optional[str] = None  # Seu api_id (número inteiro)
    TELEGRAM_API_HASH: Optional[str] = None  # Seu api_hash (string)
    TELEGRAM_PHONE: Optional[str] = None  # Seu número de telefone (formato: +55XXYYYYYYYY)

    # ================= DISCORD (for notifications) ====================
    DISCORD_WEBHOOK_URL: Optional[str] = None

    # ================= EMAIL ====================
    EMAIL_HOST: Optional[str] = None
    EMAIL_PORT: Optional[str] = None
    EMAIL_USER: Optional[str] = None
    EMAIL_PASSWORD: Optional[str] = None

    # ================= TWITTER ====================
    TWITTER_API_KEY: Optional[str] = None
    TWITTER_API_SECRET: Optional[str] = None
    TWITTER_ACCESS_TOKEN: Optional[str] = None
    TWITTER_ACCESS_TOKEN_SECRET: Optional[str] = None

    # ================= CUSTOM KEYS ====================
    # Add any custom API keys here
    CUSTOM_API_KEY_1: Optional[str] = None
    CUSTOM_API_KEY_2: Optional[str] = None

    @classmethod
    def get_all_keys(cls) -> Dict[str, Optional[str]]:
        """
        Returns all API keys as a dictionary
        Useful for debugging and validation
        """
        return {
            attr: getattr(cls, attr)
            for attr in dir(cls)
            if not attr.startswith('_') and not callable(getattr(cls, attr))
        }

    @classmethod
    def validate_required_keys(cls, required_keys: list) -> bool:
        """
        Validates if all required keys are set
        """
        for key in required_keys:
            if getattr(cls, key) is None:
                print(f"⚠️  Missing required API key: {key}")
                return False
        return True

    @classmethod
    def load_from_env(cls):
        """
        Load API keys from environment variables
        Alternative to storing them directly in this file
        """
        # Example: cls.BINANCE_API_KEY = os.getenv('BINANCE_API_KEY')
        # Add environment variable loading as needed

        # Youtube
        cls.YOUTUBE_API_KEY = os.getenv('AIzaSyAEw3uga2uUZ85-C7igQy5B3cHWr7vNV40')

        # Yahoo Finance (no key needed)
        cls.YAHOO_FINANCE_API_KEY = os.getenv('YAHOO_FINANCE_API_KEY')

        # Binance
        cls.BINANCE_API_KEY = os.getenv('BINANCE_API_KEY')
        cls.BINANCE_SECRET_KEY = os.getenv('BINANCE_SECRET_KEY')
        cls.BINANCE_TESTNET_API_KEY = os.getenv('BINANCE_TESTNET_API_KEY')
        cls.BINANCE_TESTNET_SECRET_KEY = os.getenv('BINANCE_TESTNET_SECRET_KEY')

        # Glassnode
        cls.GLASSNODE_API_KEY = os.getenv('GLASSNODE_API_KEY')

        # CoinGecko
        cls.COINGECKO_API_KEY = os.getenv('COINGECKO_API_KEY')

        # Database
        cls.DATABASE_URL = os.getenv('DATABASE_URL')
        cls.POSTGRES_USER = os.getenv('POSTGRES_USER')
        cls.POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD')
        cls.POSTGRES_HOST = os.getenv('POSTGRES_HOST')
        cls.POSTGRES_PORT = os.getenv('POSTGRES_PORT')
        cls.POSTGRES_DB = os.getenv('POSTGRES_DB')

        # Redis
        cls.REDIS_URL = os.getenv('REDIS_URL')
        cls.REDIS_HOST = os.getenv('REDIS_HOST')
        cls.REDIS_PORT = os.getenv('REDIS_PORT')
        cls.REDIS_PASSWORD = os.getenv('REDIS_PASSWORD')

# ==================== HOW TO USE ====================
"""
# Example usage in your code:

from config.api_keys import APIKeys

# Check if required keys are available
if APIKeys.BINANCE_API_KEY:
    # Use Binance API
    pass

# Load from environment variables (recommended for production)
APIKeys.load_from_env()

# Validate required keys
required = ['BINANCE_API_KEY', 'BINANCE_SECRET_KEY']
if APIKeys.validate_required_keys(required):
    print("✅ All required keys are available")
else:
    print("❌ Missing required keys")

# Get all keys (for debugging)
all_keys = APIKeys.get_all_keys()
print(f"Available keys: {list(all_keys.keys())}")
"""

# ==================== SETUP INSTRUCTIONS ====================
"""
1. Add your API keys directly above OR use environment variables
2. NEVER commit this file to version control
3. For production, use environment variables instead of hardcoding
4. Keep this file secure and limit access

# Environment Variables Setup (Recommended):
export BINANCE_API_KEY="your_binance_api_key"
export BINANCE_SECRET_KEY="your_binance_secret_key"
export GLASSNODE_API_KEY="your_glassnode_api_key"
# ... add more as needed

# Or create a .env file (also in .gitignore):
BINANCE_API_KEY=your_binance_api_key
BINANCE_SECRET_KEY=your_binance_secret_key
GLASSNODE_API_KEY=your_glassnode_api_key
"""
