import requests
import time
from datetime import datetime, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import config

# CoinGecko API base URL
COINGECKO_API_BASE_URL = "https://api.coingecko.com/api/v3"
# Delay for CoinGecko API calls
COINGECKO_API_DELAY_SECONDS = 1 # 1 second delay for simple price/change calls

# Set up a session with retry logic for robust API calls
retry_strategy = Retry(
    total=5,
    backoff_factor=2,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["HEAD", "GET", "OPTIONS"]
)
adapter = HTTPAdapter(max_retries=retry_strategy)
http = requests.Session()
http.mount("https://", adapter)
http.mount("http://", adapter)

# Dictionary to store the last portfolio alert time
last_portfolio_alert_time = {}

def get_coin_24h_change(coin_id):
    """
    Fetches the current price and 24-hour percentage change for a single coin from CoinGecko.

    Args:
        coin_id (str): The CoinGecko ID of the cryptocurrency.

    Returns:
        dict: {'price': float, 'price_change_24h': float}, or None if fetching fails.
    """
    url = f"{COINGECKO_API_BASE_URL}/simple/price"
    params = {
        "ids": coin_id,
        "vs_currencies": "usd",
        "include_24hr_change": "true"
    }
    
    try:
        response = http.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        price = data.get(coin_id, {}).get('usd')
        price_change_24h = data.get(coin_id, {}).get('usd_24h_change')
        
        if price is not None and price_change_24h is not None:
            return {'price': price, 'price_change_24h': price_change_24h}
        else:
            print(f"  Could not get 24h change data for {coin_id}.")
            return None

    except requests.exceptions.RequestException as e:
        print(f"  Error fetching 24h change for {coin_id}: {e}")
        return None
    finally:
        time.sleep(COINGECKO_API_DELAY_SECONDS)


def track_portfolio_performance():
    """
    Calculates the current value and daily performance of the user's portfolio.

    Returns:
        dict: A dictionary containing 'total_value', 'total_change_24h_percent',
              and 'individual_coins' performance.
    """
    print("\n--- Tracking portfolio performance ---")
    portfolio_data = config.PORTFOLIO_HOLDINGS
    
    if not portfolio_data:
        print("  No portfolio holdings configured. Skipping portfolio tracking.")
        return None

    total_portfolio_value = 0.0
    individual_coin_performance = {}
    
    # Store current prices and 24h changes to calculate total portfolio change
    current_prices_for_portfolio = {}
    previous_prices_for_portfolio = {} # Will store price_now / (1 + price_change_24h_percent/100)

    for coin_id, details in portfolio_data.items():
        quantity = details.get('quantity', 0.0)
        
        if quantity <= 0:
            # print(f"  Skipping {coin_id} in portfolio: quantity is zero or not specified.") # Too verbose
            continue

        coin_data = get_coin_24h_change(coin_id)
        
        if coin_data and coin_data['price'] is not None and coin_data['price_change_24h'] is not None:
            current_price = coin_data['price']
            price_change_24h = coin_data['price_change_24h'] # This is already a percentage

            current_value = current_price * quantity
            total_portfolio_value += current_value

            individual_coin_performance[coin_id] = {
                'quantity': quantity,
                'current_price': current_price,
                'current_value': current_value,
                'daily_change_percent': price_change_24h
            }
            
            # Calculate previous price for total portfolio change calculation
            # previous_price = current_price / (1 + (price_change_24h / 100))
            # previous_prices_for_portfolio[coin_id] = previous_price

            print(f"  {coin_id.replace('-', ' ').title()}: ${current_price:,.2f} ({price_change_24h:+.2f}%) - Value: ${current_value:,.2f}")
        else:
            print(f"  Could not get 24h change data for {coin_id} for portfolio tracking.")

    # Calculate total portfolio 24h change
    # This requires summing up the previous values, which means getting historical prices for each coin 24h ago.
    # CoinGecko's simple price endpoint doesn't give us historical price directly, only the change.
    # To get an accurate total portfolio 24h change, we would need to:
    # 1. Fetch current prices for all coins (which we do).
    # 2. Fetch prices from 24 hours ago for all coins (requires another API call or more complex historical data).
    # For now, we'll use a simplified approach by calculating the weighted average of individual changes,
    # or just report individual changes if a robust total 24h change isn't feasible with free APIs.

    # Simplified total portfolio change calculation (weighted average of individual changes)
    total_change_24h_percent = 0.0
    if total_portfolio_value > 0:
        for coin_id, perf_data in individual_coin_performance.items():
            weight = perf_data['current_value'] / total_portfolio_value
            total_change_24h_percent += weight * perf_data['daily_change_percent']

    print(f"  Total Portfolio Value: ${total_portfolio_value:,.2f}")
    print(f"  Total Portfolio 24h Change: {total_change_24h_percent:+.2f}%")

    return {
        'total_value': total_portfolio_value,
        'total_change_24h_percent': total_change_24h_percent,
        'individual_coins': individual_coin_performance
    }


def send_portfolio_alert(portfolio_summary):
    """
    Checks if portfolio performance triggers an alert and sends a Discord notification.
    """
    webhook_url = config.DISCORD_WEBHOOK_URL
    if not webhook_url or webhook_url == "YOUR_DISCORD_WEBHOOK_URL_HERE":
        print("  Discord Webhook URL not configured. Skipping portfolio alerts.")
        return False

    current_time = datetime.now()
    cooldown_hours = config.PORTFOLIO_ALERT_COOLDOWN_HOURS

    # Check cooldown for portfolio alerts
    if 'portfolio_alert' in last_portfolio_alert_time:
        time_since_last_alert = (current_time - last_portfolio_alert_time['portfolio_alert']).total_seconds() / 3600
        if time_since_last_alert < cooldown_hours:
            print(f"  Portfolio is on alert cooldown. Last alert was {time_since_last_alert:.1f} hours ago. Skipping portfolio alert check.")
            return False

    alert_triggered = False
    alert_messages = []

    total_change_threshold = config.PORTFOLIO_ALERT_THRESHOLDS.get('total_portfolio_percent_change')
    individual_change_threshold = config.PORTFOLIO_ALERT_THRESHOLDS.get('individual_coin_percent_change')

    # Check total portfolio change
    if total_change_threshold is not None and portfolio_summary['total_change_24h_percent'] is not None:
        if abs(portfolio_summary['total_change_24h_percent']) >= total_change_threshold:
            alert_messages.append(f"Total portfolio changed **{portfolio_summary['total_change_24h_percent']:+.2f}%** in 24h (threshold: {total_change_threshold}%)!")
            alert_triggered = True

    # Check individual coin changes
    if individual_change_threshold is not None:
        for coin_id, perf_data in portfolio_summary['individual_coins'].items():
            if perf_data['daily_change_percent'] is not None and abs(perf_data['daily_change_percent']) >= individual_change_threshold:
                alert_messages.append(f"{coin_id.replace('-', ' ').title()} changed **{perf_data['daily_change_percent']:+.2f}%** in 24h (threshold: {individual_change_threshold}%)!")
                alert_triggered = True

    if alert_triggered:
        embed_color = 3066993 if portfolio_summary['total_change_24h_percent'] >= 0 else 15158332 # Green for gain, Red for loss
        
        embed = {
            "title": "📈 Portfolio Performance Alert 📉",
            "description": "\n".join(alert_messages),
            "color": embed_color,
            "fields": [
                {"name": "Total Portfolio Value", "value": f"${portfolio_summary['total_value']:,.2f}", "inline": True},
                {"name": "Total 24h Change", "value": f"{portfolio_summary['total_change_24h_percent']:+.2f}%", "inline": True}
            ],
            "footer": {
                "text": f"Portfolio alert generated at {current_time.strftime('%Y-%m-%d %H:%M:%S')} UTC"
            }
        }

        # Add individual coin details to fields if there are many and space allows, or summarize
        # For now, keeping it concise and relying on description for individual alerts
        
        payload = {"embeds": [embed]}

        try:
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            print(f"  Discord portfolio alert sent successfully.")
            last_portfolio_alert_time['portfolio_alert'] = current_time
            return True
        except requests.exceptions.RequestException as e:
            print(f"  Error sending Discord portfolio alert: {e}")
            return False
    
    return False

# Example usage (for testing purposes, not part of the main agent flow)
if __name__ == "__main__":
    print("--- Testing portfolio_tracker.py ---")

    # To test properly, ensure config.py has PORTFOLIO_HOLDINGS and PORTFOLIO_ALERT_THRESHOLDS set.
    # Example:
    # PORTFOLIO_HOLDINGS = {
    #     'solana': {'quantity': 10.0},
    #     'chainlink': {'quantity': 5.0}
    # }
    # PORTFOLIO_ALERT_THRESHOLDS = {
    #     'total_portfolio_percent_change': 1.0, # Alert if total portfolio changes +/- 1%
    #     'individual_coin_percent_change': 2.0  # Alert if any coin changes +/- 2%
    # }

    # Simulate a run
    portfolio_summary = track_portfolio_performance()
    
    if portfolio_summary:
        print("\nPortfolio Summary:")
        print(f"Total Value: ${portfolio_summary['total_value']:,.2f}")
        print(f"Total 24h Change: {portfolio_summary['total_change_24h_percent']:+.2f}%")
        print("Individual Coins:")
        for coin, data in portfolio_summary['individual_coins'].items():
            print(f"  {coin.replace('-', ' ').title()}: ${data['current_price']:,.2f} ({data['daily_change_percent']:+.2f}%) - Value: ${data['current_value']:,.2f}")
        
        # Attempt to send alert
        alert_sent = send_portfolio_alert(portfolio_summary)
        print(f"\nPortfolio alert sent status: {alert_sent}")
    else:
        print("Portfolio tracking could not be performed.")

    print("\n--- Test complete ---")
