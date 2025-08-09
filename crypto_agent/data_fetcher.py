import requests
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# CoinGecko API base URL
COINGECKO_API_BASE_URL = "https://api.coingecko.com/api/v3"
# Delay between CoinGecko API calls to respect rate limits (e.g., 10-30 calls/minute for free tier)
# We'll use 6 seconds for historical data fetches to be safe (10 calls per minute)
COINGECKO_HISTORICAL_API_DELAY_SECONDS = 6
# For simple price fetches, we can be faster, but still need a small delay
COINGECKO_SIMPLE_PRICE_API_DELAY_SECONDS = 1 # 1 second delay = 60 calls/minute max, but we'll manage calls in main.py

# Set up a session with retry logic for robust API calls
# This helps handle temporary network issues or rate limits
retry_strategy = Retry(
    total=5,  # Maximum number of retries
    backoff_factor=2,  # Exponential backoff (1s, 2s, 4s, 8s, 16s delays)
    status_forcelist=[429, 500, 502, 503, 504],  # HTTP status codes to retry on
    allowed_methods=["HEAD", "GET", "OPTIONS"] # Methods to retry
)
adapter = HTTPAdapter(max_retries=retry_strategy)
http = requests.Session()
http.mount("https://", adapter)
http.mount("http://", adapter)

def _get_coingecko_data(coin_id, days=250): # Increased days for 200D EMA
    """
    Fetches historical market data (prices, market caps, volumes) for a given coin from CoinGecko.
    
    Args:
        coin_id (str): The CoinGecko ID of the cryptocurrency (e.g., 'solana').
        days (int): Number of days of historical data to fetch.
                    Increased to ~250 for 200-day EMA calculation.

    Returns:
        pd.DataFrame: A DataFrame with 'timestamp', 'price', and 'volume' columns,
                      or an empty DataFrame if data fetching fails.
    """
    url = f"{COINGECKO_API_BASE_URL}/coins/{coin_id}/market_chart"
    params = {
        "vs_currency": "usd",
        "days": days,
        "interval": "daily" # Using daily interval for sufficient data points for indicators
    }
    
    print(f"  Fetching historical data for {coin_id} from CoinGecko (for {days} days)...")
    try:
        response = http.get(url, params=params, timeout=10) # Add a timeout for the request
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
        data = response.json()

        prices = data.get('prices', [])
        volumes = data.get('total_volumes', [])

        if not prices or not volumes:
            print(f"  No price or volume data found for {coin_id}.")
            return pd.DataFrame()

        # Convert timestamps to datetime objects and create DataFrame
        df_prices = pd.DataFrame(prices, columns=['timestamp', 'price'])
        df_volumes = pd.DataFrame(volumes, columns=['timestamp', 'volume'])

        # Merge on timestamp and convert timestamp to readable datetime
        df = pd.merge(df_prices, df_volumes, on='timestamp')
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df.set_index('timestamp').sort_index()

        print(f"  Successfully fetched {len(df)} data points for {coin_id}.")
        return df

    except requests.exceptions.RequestException as e:
        print(f"  Error fetching historical data for {coin_id} from CoinGecko: {e}")
        return pd.DataFrame()
    finally:
        # Respect CoinGecko API rate limits
        time.sleep(COINGECKO_HISTORICAL_API_DELAY_SECONDS)

def get_current_price(coin_id):
    """
    Fetches only the current price for a given coin from CoinGecko.
    This is a lightweight call for frequent price checks.

    Args:
        coin_id (str): The CoinGecko ID of the cryptocurrency.

    Returns:
        float: The current price, or None if fetching fails.
    """
    url = f"{COINGECKO_API_BASE_URL}/simple/price"
    params = {
        "ids": coin_id,
        "vs_currencies": "usd"
    }
    
    try:
        response = http.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        price = data.get(coin_id, {}).get('usd')
        
        return price

    except requests.exceptions.RequestException as e:
        print(f"  Error fetching current price for {coin_id}: {e}")
        return None
    finally:
        time.sleep(COINGECKO_SIMPLE_PRICE_API_DELAY_SECONDS)

def get_coin_ath(coin_id):
    """
    Fetches the all-time high (ATH) price for a given coin from CoinGecko.

    Args:
        coin_id (str): The CoinGecko ID of the cryptocurrency.

    Returns:
        float: The ATH price, or None if fetching fails.
    """
    url = f"{COINGECKO_API_BASE_URL}/coins/{coin_id}"
    params = {
        "localization": "false",
        "tickers": "false",
        "market_data": "true",
        "community_data": "false",
        "developer_data": "false",
        "sparkline": "false"
    }

    print(f"  Fetching ATH for {coin_id} from CoinGecko...")
    try:
        response = http.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        ath = data.get('market_data', {}).get('ath', {}).get('usd')
        
        if ath is not None:
            print(f"  ATH for {coin_id}: ${ath:,.2f}")
        else:
            print(f"  Could not get ATH for {coin_id}.")
        return ath

    except requests.exceptions.RequestException as e:
        print(f"  Error fetching ATH for {coin_id}: {e}")
        return None
    finally:
        time.sleep(COINGECKO_HISTORICAL_API_DELAY_SECONDS)

def get_btc_dominance_calculated():
    """
    Calculates Bitcoin's market dominance by fetching BTC's market cap
    and the total crypto market cap, then performing the calculation.

    Returns:
        float: Calculated Bitcoin dominance percentage, or None if fetching fails.
    """
    print("  Calculating BTC dominance from market caps...")
    url = f"{COINGECKO_API_BASE_URL}/simple/price"
    params = {
        "ids": "bitcoin",
        "vs_currencies": "usd",
        "include_market_cap": "true"
    }
    
    try:
        btc_response = http.get(url, params=params, timeout=10)
        btc_response.raise_for_status()
        btc_data = btc_response.json()
        
        btc_market_cap = btc_data.get('bitcoin', {}).get('usd_market_cap')
        
        if btc_market_cap is None:
            print("  Could not get Bitcoin market cap for dominance calculation.")
            return None

        # Fetch total market cap from CoinGecko's global data endpoint
        global_url = f"{COINGECKO_API_BASE_URL}/global"
        global_response = http.get(global_url, timeout=10)
        global_response.raise_for_status()
        global_data = global_response.json()
        
        total_market_cap = global_data.get('data', {}).get('total_market_cap', {}).get('usd')

        if total_market_cap is None:
            print("  Could not get total crypto market cap for dominance calculation.")
            return None

        btc_dominance = (btc_market_cap / total_market_cap) * 100
        
        print(f"  Calculated BTC Dominance: {btc_dominance:.2f}%")
        return btc_dominance

    except requests.exceptions.RequestException as e:
        print(f"  Error calculating BTC dominance: {e}")
        return None
    finally:
        time.sleep(COINGECKO_HISTORICAL_API_DELAY_SECONDS)


def _calculate_rsi(prices, window=14):
    """
    Calculates the Relative Strength Index (RSI).

    Args:
        prices (pd.Series): A pandas Series of closing prices.
        window (int): The look-back period for RSI calculation (default: 14).

    Returns:
        float: The latest RSI value, or None if not enough data.
    """
    if len(prices) < window + 1:
        return None

    delta = prices.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.ewm(com=window - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=window - 1, adjust=False).mean()

    if avg_loss.iloc[-1] == 0:
        rs = pd.Series(np.inf, index=avg_gain.index)
    else:
        rs = avg_gain / avg_loss
        
    rsi = 100 - (100 / (1 + rs))
    
    return rsi.iloc[-1] if not rsi.empty else None

def _calculate_ema(prices, window):
    """
    Calculates the Exponential Moving Average (EMA).

    Args:
        prices (pd.Series): A pandas Series of closing prices.
        window (int): The look-back period for EMA calculation.

    Returns:
        float: The latest EMA value, or None if not enough data.
    """
    if len(prices) < window:
        return None
    ema = prices.ewm(span=window, adjust=False).mean()
    return ema.iloc[-1] if not ema.empty else None

def _calculate_bollinger_bands(prices, window=20, num_std_dev=2):
    """
    Calculates Bollinger Bands (Middle Band, Upper Band, Lower Band).

    Args:
        prices (pd.Series): A pandas Series of closing prices.
        window (int): The look-back period for SMA and standard deviation (default: 20).
        num_std_dev (int): The number of standard deviations for the bands (default: 2).

    Returns:
        dict: A dictionary containing 'upper', 'middle', and 'lower' band values,
              or None if not enough data.
    """
    if len(prices) < window:
        return None

    sma = prices.rolling(window=window).mean()
    std_dev = prices.rolling(window=window).std()

    upper_band = sma + (std_dev * num_std_dev)
    lower_band = sma - (std_dev * num_std_dev)
    middle_band = sma

    if not upper_band.empty and not lower_band.empty and not middle_band.empty:
        return {
            "upper": upper_band.iloc[-1],
            "middle": middle_band.iloc[-1],
            "lower": lower_band.iloc[-1]
        }
    return None

def fetch_data(coin_id):
    """
    Main function to fetch data and compute all technical indicators for a given coin.
    This is used for the slower, comprehensive signal analysis loop.

    Args:
        coin_id (str): The CoinGecko ID of the cryptocurrency.

    Returns:
        dict: A dictionary containing the latest price, volume, and calculated indicators.
              Returns default/None values if data is insufficient or fetching fails.
    """
    print(f"  Starting comprehensive data fetch for {coin_id}...")
    
    # Fetch historical data for 200D EMA and recent price changes
    # Need at least 200 data points for EMA200. Fetching 250 days to be safe.
    df = _get_coingecko_data(coin_id, days=250)

    if df.empty:
        print(f"  Could not retrieve sufficient historical data for {coin_id}. Returning default values.")
        return {
            "price": None,
            "volume": None,
            "rsi": None,
            "ema20": None,
            "ema50": None,
            "ema200": None, # Added
            "bollinger_bands": {"upper": None, "middle": None, "lower": None},
            "price_change_7d_percent": None, # Added
            "price_change_30d_percent": None # Added
        }

    latest_price = df['price'].iloc[-1]
    latest_volume = df['volume'].iloc[-1]

    # Calculate indicators
    rsi = _calculate_rsi(df['price'], window=14)
    ema20 = _calculate_ema(df['price'], window=20)
    ema50 = _calculate_ema(df['price'], window=50)
    ema200 = _calculate_ema(df['price'], window=200) # New: 200-day EMA
    bollinger_bands = _calculate_bollinger_bands(df['price'], window=20, num_std_dev=2)

    # Calculate recent price changes for parabolic detection
    price_change_7d_percent = None
    if len(df['price']) >= 7:
        price_7d_ago = df['price'].iloc[-7]
        if price_7d_ago > 0:
            price_change_7d_percent = ((latest_price - price_7d_ago) / price_7d_ago) * 100

    price_change_30d_percent = None
    if len(df['price']) >= 30:
        price_30d_ago = df['price'].iloc[-30]
        if price_30d_ago > 0:
            price_change_30d_percent = ((latest_price - price_30d_ago) / price_30d_ago) * 100

    return {
        "price": latest_price,
        "volume": latest_volume,
        "rsi": rsi,
        "ema20": ema20,
        "ema50": ema50,
        "ema200": ema200,
        "bollinger_bands": bollinger_bands,
        "price_change_7d_percent": price_change_7d_percent,
        "price_change_30d_percent": price_change_30d_percent
    }
