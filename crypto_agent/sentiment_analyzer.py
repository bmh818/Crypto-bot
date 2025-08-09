import requests
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from pytrends.request import TrendReq
from datetime import datetime, timedelta

# CoinMarketCap API base URL for Fear and Greed Index
# Note: This API provides a market-wide sentiment index, not coin-specific sentiment.
CMC_FGI_API_URL = "https://pro-api.coinmarketcap.com/v3/fear-and-greed/historical"
# You might need a CoinMarketCap API key for this.
# For the free tier, it's often included in the request if you register.
# If you encounter issues, check CoinMarketCap API documentation for free tier limits.

# Delay between CoinMarketCap API calls to respect rate limits (e.g., 10-30 calls/minute for free tier)
CMC_API_DELAY_SECONDS = 6

# Set up a session with retry logic for robust API calls for CoinMarketCap
retry_strategy_cmc = Retry(
    total=5,  # Maximum number of retries
    backoff_factor=2,  # Exponential backoff (1s, 2s, 4s, 8s, 16s delays)
    status_forcelist=[429, 500, 502, 503, 504],  # HTTP status codes to retry on
    allowed_methods=["HEAD", "GET", "OPTIONS"] # Methods to retry
)
adapter_cmc = HTTPAdapter(max_retries=retry_strategy_cmc)
http_cmc = requests.Session()
http_cmc.mount("https://", adapter_cmc)
http_cmc.mount("http://", adapter_cmc)

# Initialize pytrends for Google Trends
# hl: host language, tz: timezone offset (e.g., 360 for US Central Time)
pytrends = TrendReq(hl='en-US', tz=360)

def _get_cmc_fear_greed_index():
    """
    Fetches the latest market sentiment score from CoinMarketCap's Fear and Greed Index.
    """
    print("  Fetching market-wide Fear and Greed Index...")
    params = {"limit": 1}
    headers = {
        'Accepts': 'application/json',
        'X-CMC_PRO_API_KEY': '691ad23a-ac35-4c9b-b188-f148eb82bc80' # Your API key has been added here
    }

    try:
        response = http_cmc.get(CMC_FGI_API_URL, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        fgi_data = data.get('data', [])
        
        if not fgi_data:
            print("  No Fear and Greed Index data found.")
            return {"sentiment_score": None, "sentiment_category": "N/A"}

        latest_fgi = fgi_data[0]
        score = latest_fgi.get('value')
        category = latest_fgi.get('value_classification')

        print(f"  Latest Market Sentiment (FGI): Score = {score}, Category = {category}")
        return {"sentiment_score": float(score) if score else None, "sentiment_category": category}

    except requests.exceptions.RequestException as e:
        print(f"  Error fetching market sentiment from CoinMarketCap FGI: {e}")
        return {"sentiment_score": None, "sentiment_category": "Error"}
    finally:
        time.sleep(CMC_API_DELAY_SECONDS) # Respect API rate limits

def _get_google_trends_interest(keyword):
    """
    Fetches Google Trends interest over time for a given keyword.
    The interest is normalized from 0-100, where 100 is peak popularity.

    Args:
        keyword (str): The search term for Google Trends (e.g., 'solana coin').

    Returns:
        float: The average interest score for the last 7 days, or None if data is unavailable.
    """
    print(f"  Fetching Google Trends interest for '{keyword}'...")
    try:
        # Define the time period for the last 7 days
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        timeframe = f"{start_date.strftime('%Y-%m-%d')} {end_date.strftime('%Y-%m-%d')}"

        pytrends.build_payload([keyword], cat=0, timeframe=timeframe, geo='', gprop='')
        interest_df = pytrends.interest_over_time()

        if interest_df.empty or keyword not in interest_df.columns:
            print(f"  No Google Trends data found for '{keyword}'.")
            return None
        
        # Google Trends returns interest values from 0-100.
        # We'll take the average of the last few days as a current indicator.
        # Exclude 'isPartial' column if present
        interest_data = interest_df[keyword].iloc[-7:] # Last 7 data points
        average_interest = interest_data.mean()
        
        print(f"  Google Trends interest for '{keyword}': {average_interest:.2f}")
        return average_interest

    except Exception as e:
        print(f"  Error fetching Google Trends data for '{keyword}': {e}")
        return None

def analyze_sentiment(coin_id):
    """
    Combines market-wide sentiment (Fear and Greed Index) and coin-specific
    public interest (Google Trends) for a given coin.

    Args:
        coin_id (str): The CoinGecko ID of the cryptocurrency (used for Google Trends keyword).

    Returns:
        dict: A dictionary containing the FGI score/category and Google Trends interest.
              Returns default/None values if data fetching fails.
    """
    sentiment_results = {}

    # Get market-wide Fear and Greed Index
    fgi_data = _get_cmc_fear_greed_index()
    sentiment_results['fgi_score'] = fgi_data.get('sentiment_score')
    sentiment_results['fgi_category'] = fgi_data.get('sentiment_category')

    # Get coin-specific Google Trends interest
    # For Google Trends, use a more user-friendly name if available, otherwise coin_id
    # You might want to map CoinGecko IDs to more common search terms in config.py
    # For example, 'solana' -> 'solana crypto', 'sui' -> 'sui coin'
    google_trends_keyword = coin_id.replace('-', ' ') + ' coin' # Simple heuristic
    trends_interest = _get_google_trends_interest(google_trends_keyword)
    sentiment_results['google_trends_interest'] = trends_interest

    return sentiment_results

# Example usage (for testing purposes, not part of the main agent flow)
if __name__ == "__main__":
    print("--- Testing sentiment_analyzer.py ---")
    test_coin_id = 'solana'
    sentiment_data = analyze_sentiment(test_coin_id)
    print(f"\nCombined sentiment data for {test_coin_id}:")
    print(f"  FGI Score: {sentiment_data.get('fgi_score')}")
    print(f"  FGI Category: {sentiment_data.get('fgi_category')}")
    print(f"  Google Trends Interest: {sentiment_data.get('google_trends_interest')}")
    print("\n--- Test complete ---")
