import requests
import json
import time
from datetime import datetime, timedelta

# Import configuration settings
import config

# Dictionaries to store the last alert time for each coin to manage cooldowns
last_signal_alert_times = {}
last_price_alert_times = {}
last_top_detection_alert_times = {}
last_dip_buy_alert_times = {}
last_profit_taking_alert_times = {}
last_trailing_stop_alert_times = {} # New: for trailing stop alerts

def _send_discord_message(title, description, color, fields, footer, webhook_url):
    """
    Helper function to send a Discord embed message with robust error handling.
    """
    if not webhook_url or webhook_url == "YOUR_DISCORD_WEBHOOK_URL_HERE":
        print("  Discord Webhook URL not configured. Skipping message.")
        return False

    embed = {
        "title": title,
        "description": description,
        "color": color,
        "fields": fields,
        "footer": footer
    }

    payload = {"embeds": [embed]}

    try:
        response = requests.post(webhook_url, json=payload, timeout=15) # Increased timeout for robustness
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
        return True
    except requests.exceptions.RequestException as e:
        print(f"  Error sending Discord message: {e}")
        print(f"  Attempted URL: {webhook_url}")
        return False

def send_discord_alert(coin_id, score, details):
    """
    Sends a nicely formatted signal alert message to the Discord webhook if the signal score
    is above the threshold and the cooldown for the coin has passed.

    Args:
        coin_id (str): The ID of the cryptocurrency.
        score (float): The calculated signal score (0-100).
        details (dict): A dictionary containing detailed data and sentiment for the alert.
                        Expected keys: 'data' (from data_fetcher), 'sentiment' (from sentiment_analyzer).
    """
    current_time = datetime.now()
    cooldown_hours = config.ALERT_COOLDOWN_HOURS
    
    # Check if the coin is on cooldown for signal alerts
    if coin_id in last_signal_alert_times:
        time_since_last_alert = (current_time - last_signal_alert_times[coin_id]).total_seconds() / 3600
        if time_since_last_alert < cooldown_hours:
            print(f"  {coin_id} is on SIGNAL alert cooldown. Last alert was {time_since_last_alert:.1f} hours ago. Skipping signal alert.")
            return False

    if score < config.ALERT_SCORE_THRESHOLD:
        print(f"  Signal score {score:.2f} for {coin_id} is below threshold {config.ALERT_SCORE_THRESHOLD}. Skipping signal alert.")
        return False

    print(f"  Signal strong enough for {coin_id} (Score: {score:.2f}). Preparing Discord signal alert...")

    # Extract relevant details for the embed
    price = details.get('data', {}).get('price')
    volume = details.get('data', {}).get('volume')
    rsi = details.get('data', {}).get('rsi')
    ema20 = details.get('data', {}).get('ema20')
    ema50 = details.get('data', {}).get('ema50')
    bb = details.get('data', {}).get('bollinger_bands', {})
    fgi_score = details.get('sentiment', {}).get('fgi_score')
    fgi_category = details.get('sentiment', {}).get('fgi_category')
    google_trends_interest = details.get('sentiment', {}).get('google_trends_interest')

    fields = [
        {"name": "Signal Score", "value": f"{score:.2f}/100", "inline": True},
        {"name": "Current Price", "value": f"${price:,.2f}" if price is not None else "N/A", "inline": True},
        {"name": "24h Volume", "value": f"${volume:,.0f}" if volume is not None else "N/A", "inline": True},
        {"name": "RSI (14)", "value": f"{rsi:.2f}" if rsi is not None else "N/A", "inline": True},
        {"name": "EMA20", "value": f"{ema20:.2f}" if ema20 is not None else "N/A", "inline": True},
        {"name": "EMA50", "value": f"{ema50:.2f}" if ema50 is not None else "N/A", "inline": True},
    ]

    if bb.get('upper') is not None:
        fields.extend([
            {"name": "BB Upper", "value": f"{bb['upper']:.2f}", "inline": True},
            {"name": "BB Middle", "value": f"{bb['middle']:.2f}", "inline": True},
            {"name": "BB Lower", "value": f"{bb['lower']:.2f}", "inline": True}
        ])

    if fgi_score is not None:
        fields.append({"name": "FGI Score", "value": f"{fgi_score:.1f} ({fgi_category})", "inline": True})
    if google_trends_interest is not None:
        fields.append({"name": "Google Trends", "value": f"{google_trends_interest:.1f}", "inline": True})

    title = f"🚨 Crypto Signal Alert: {coin_id.replace('-', ' ').title()} 🚨"
    description = f"A strong signal detected for {coin_id.replace('-', ' ').title()}!"
    color = 16763904 # Orange
    footer = {"text": f"Signal alert generated at {current_time.strftime('%Y-%m-%d %H:%M:%S')} UTC"}

    if _send_discord_message(title, description, color, fields, footer, config.DISCORD_WEBHOOK_URL):
        last_signal_alert_times[coin_id] = current_time
        return True
    return False

def check_price_alerts(coin_id, current_price):
    """
    Checks if the current price of a coin triggers any predefined price alerts
    and sends a Discord notification if so, respecting cooldowns.

    Args:
        coin_id (str): The ID of the cryptocurrency.
        current_price (float): The current price of the cryptocurrency.

    Returns:
        bool: True if a price alert was sent, False otherwise.
    """
    price_targets = config.PRICE_ALERTS.get(coin_id)
    if not price_targets:
        return False

    current_time = datetime.now()
    cooldown_hours = config.PRICE_ALERT_COOLDOWN_HOURS

    if coin_id in last_price_alert_times:
        time_since_last_alert = (current_time - last_price_alert_times[coin_id]).total_seconds() / 3600
        if time_since_last_alert < cooldown_hours:
            print(f"  {coin_id} is on PRICE alert cooldown. Last alert was {time_since_last_alert:.1f} hours ago. Skipping price alert check.")
            return False

    alert_sent = False
    alert_type = None
    target_price = None

    buy_target = price_targets.get('buy')
    sell_target = price_targets.get('sell')

    if buy_target is not None and current_price <= buy_target:
        alert_type = "BUY"
        target_price = buy_target
        print(f"  Price alert triggered: {coin_id.replace('-', ' ').title()} is at or below BUY target ${buy_target:,.2f}")
    elif sell_target is not None and current_price >= sell_target:
        alert_type = "SELL"
        target_price = sell_target
        print(f"  Price alert triggered: {coin_id.replace('-', ' ').title()} is at or above SELL target ${sell_target:,.2f}")

    if alert_type:
        title = f"🔔 Price Alert: {coin_id.replace('-', ' ').title()} 🔔"
        description = f"**{alert_type} Target Reached!**"
        color = 3447003 if alert_type == "BUY" else 15158332 # Green for Buy, Red for Sell
        fields = [
            {"name": "Coin", "value": coin_id.replace('-', ' ').title(), "inline": True},
            {"name": "Current Price", "value": f"${current_price:,.2f}", "inline": True},
            {"name": f"{alert_type} Target", "value": f"${target_price:,.2f}", "inline": True}
        ]
        footer = {"text": f"Price alert generated at {current_time.strftime('%Y-%m-%d %H:%M:%S')} UTC"}

        if _send_discord_message(title, description, color, fields, footer, config.DISCORD_WEBHOOK_URL):
            last_price_alert_times[coin_id] = current_time
            alert_sent = True
    
    return alert_sent

def send_top_detection_alert(coin_id, price, rsi, ema200, parabolic_factor):
    """
    Sends a 'top detection' alert for potential profit-taking.
    """
    current_time = datetime.now()
    cooldown_hours = config.ALERT_COOLDOWN_HOURS # Using general alert cooldown for now
    
    if coin_id in last_top_detection_alert_times:
        time_since_last_alert = (current_time - last_top_detection_alert_times[coin_id]).total_seconds() / 3600
        if time_since_last_alert < cooldown_hours:
            print(f"  {coin_id} is on TOP DETECTION alert cooldown. Last alert was {time_since_last_alert:.1f} hours ago. Skipping alert.")
            return False

    print(f"  Top detection alert triggered for {coin_id.replace('-', ' ').title()}. Preparing Discord alert...")

    title = f"⚠️ Top Detection Alert: {coin_id.replace('-', ' ').title()} ⚠️"
    description = f"**Potential Profit-Taking Opportunity!**\n" \
                  f"This asset shows signs of being overbought and a parabolic move."
    color = 16711680 # Red color for warning
    fields = [
        {"name": "Current Price", "value": f"${price:,.2f}", "inline": True},
        {"name": "RSI (14)", "value": f"{rsi:.2f}", "inline": True},
        {"name": "200D EMA", "value": f"{ema200:.2f}", "inline": True},
        {"name": "Parabolic Factor", "value": f"{parabolic_factor:.2f}x", "inline": True},
        {"name": "Recommendation", "value": "Consider taking profits.", "inline": False}
    ]
    footer = {"text": f"Top detection alert generated at {current_time.strftime('%Y-%m-%d %H:%M:%S')} UTC"}

    if _send_discord_message(title, description, color, fields, footer, config.DISCORD_WEBHOOK_URL):
        last_top_detection_alert_times[coin_id] = current_time
        return True
    return False

def send_dip_buy_alert(coin_id, price, rsi, ema20, bb_lower, price_change_7d):
    """
    Sends a 'dip buy' alert for potential accumulation.
    """
    current_time = datetime.now()
    cooldown_hours = config.ALERT_COOLDOWN_HOURS # Using general alert cooldown for now
    
    if coin_id in last_dip_buy_alert_times:
        time_since_last_alert = (current_time - last_dip_buy_alert_times[coin_id]).total_seconds() / 3600
        if time_since_last_alert < cooldown_hours:
            print(f"  {coin_id} is on DIP BUY alert cooldown. Last alert was {time_since_last_alert:.1f} hours ago. Skipping alert.")
            return False

    print(f"  Dip buy alert triggered for {coin_id.replace('-', ' ').title()}. Preparing Discord alert...")

    title = f"🟢 Dip Buy Alert: {coin_id.replace('-', ' ').title()} 🟢"
    description = f"**Potential Buying Opportunity!**\n" \
                  f"This asset shows signs of a healthy retracement or dip."
    color = 3066993 # Green color for buy signal
    fields = [
        {"name": "Current Price", "value": f"${price:,.2f}", "inline": True},
        {"name": "RSI (14)", "value": f"{rsi:.2f}", "inline": True},
        {"name": "EMA20", "value": f"{ema20:.2f}", "inline": True},
        {"name": "BB Lower", "value": f"{bb_lower:.2f}" if bb_lower is not None else "N/A", "inline": True},
        {"name": "7D Change", "value": f"{price_change_7d:+.2f}%" if price_change_7d is not None else "N/A", "inline": True},
        {"name": "Recommendation", "value": "Consider accumulating.", "inline": False}
    ]
    footer = {"text": f"Dip buy alert generated at {current_time.strftime('%Y-%m-%d %H:%M:%S')} UTC"}

    if _send_discord_message(title, description, color, fields, footer, config.DISCORD_WEBHOOK_URL):
        last_dip_buy_alert_times[coin_id] = current_time
        return True
    return False

def send_profit_taking_alert(coin_id, current_price, target_price, sell_percentage, current_holdings_quantity):
    """
    Sends a 'profit-taking' alert when a specific price target is hit.
    """
    current_time = datetime.now()
    cooldown_hours = config.PROFIT_TAKING_ALERT_COOLDOWN_HOURS
    
    # Create a unique key for this specific target to manage cooldowns per target
    alert_key = (coin_id, target_price) 

    if alert_key in last_profit_taking_alert_times:
        time_since_last_alert = (current_time - last_profit_taking_alert_times[alert_key]).total_seconds() / 3600
        if time_since_last_alert < cooldown_hours:
            print(f"  {coin_id} at target ${target_price:,.2f} is on PROFIT-TAKING alert cooldown. Last alert was {time_since_last_alert:.1f} hours ago. Skipping alert.")
            return False

    print(f"  Profit-taking alert triggered for {coin_id.replace('-', ' ').title()} at target ${target_price:,.2f}. Preparing Discord alert...")

    # Calculate recommended amount to sell
    recommended_sell_quantity = (sell_percentage / 100.0) * current_holdings_quantity
    estimated_profit_value = recommended_sell_quantity * current_price

    title = f"💰 Profit-Taking Alert: {coin_id.replace('-', ' ').title()} 💰"
    description = f"**Target Price Hit! Consider taking profits.**"
    color = 16744448 # Gold/Yellow color for profit
    fields = [
        {"name": "Current Price", "value": f"${current_price:,.2f}", "inline": True},
        {"name": "Target Price", "value": f"${target_price:,.2f}", "inline": True},
        {"name": "Recommendation", "value": f"Sell **{sell_percentage:.0f}%** of your holdings.", "inline": True},
        {"name": "Estimated Quantity", "value": f"{recommended_sell_quantity:,.4f} {coin_id.replace('-', ' ').upper()}", "inline": True},
        {"name": "Estimated Value", "value": f"${estimated_profit_value:,.2f}", "inline": True}
    ]
    footer = {"text": f"Profit-taking alert generated at {current_time.strftime('%Y-%m-%d %H:%M:%S')} UTC"}

    if _send_discord_message(title, description, color, fields, footer, config.DISCORD_WEBHOOK_URL):
        last_profit_taking_alert_times[alert_key] = current_time # Update cooldown using the unique key
        return True
    return False

def send_trailing_stop_alert(coin_id, price, ath=None, drop_percent=None, ema50=None, close_below_ema=False):
    """
    Sends a 'trailing stop' alert for risk management or trend breakdown.
    """
    current_time = datetime.now()
    cooldown_hours = config.TRAILING_STOP_ALERT_COOLDOWN_HOURS
    
    # Create a unique key for this specific alert type for cooldown management
    alert_key = coin_id
    if drop_percent is not None:
        alert_key = (coin_id, f"ATH_DROP_{drop_percent}")
    elif close_below_ema:
        alert_key = (coin_id, "CLOSE_BELOW_EMA50")

    if alert_key in last_trailing_stop_alert_times:
        time_since_last_alert = (current_time - last_trailing_stop_alert_times[alert_key]).total_seconds() / 3600
        if time_since_last_alert < cooldown_hours:
            print(f"  {coin_id} TRAILING STOP alert is on cooldown. Last alert was {time_since_last_alert:.1f} hours ago. Skipping alert.")
            return False

    print(f"  Trailing Stop alert triggered for {coin_id.replace('-', ' ').title()}. Preparing Discord alert...")

    title = f"🛑 Trailing Stop Alert: {coin_id.replace('-', ' ').title()} 🛑"
    description = f"**Potential Exit Signal!**\n" \
                  f"This asset shows signs of a trend reversal or significant pullback."
    color = 10038562 # Dark Red/Maroon for stop loss
    fields = [
        {"name": "Current Price", "value": f"${price:,.2f}", "inline": True}
    ]

    if ath is not None and drop_percent is not None:
        fields.append({"name": "Drop from ATH", "value": f"{drop_percent:.2f}%", "inline": True})
        fields.append({"name": "All-Time High", "value": f"${ath:,.2f}", "inline": True})
        
    if ema50 is not None and close_below_ema:
        fields.append({"name": "50D EMA", "value": f"${ema50:,.2f}", "inline": True})
        fields.append({"name": "Condition", "value": "Closed below 50D EMA", "inline": True})
    
    fields.append({"name": "Recommendation", "value": "Consider re-evaluating your position.", "inline": False})

    footer = {"text": f"Trailing Stop alert generated at {current_time.strftime('%Y-%m-%d %H:%M:%S')} UTC"}

    if _send_discord_message(title, description, color, fields, footer, config.DISCORD_WEBHOOK_URL):
        last_trailing_stop_alert_times[alert_key] = current_time
        return True
    return False


# Example usage (for testing purposes, not part of the main agent flow)
if __name__ == "__main__":
    print("--- Testing discord_alert.py with all alert types ---")

    # IMPORTANT: Replace with a real Discord webhook URL in config.py for testing!
    # If config.DISCORD_WEBHOOK_URL is still the placeholder, these tests will print messages.
    
    test_coin = 'solana'
    test_score_high = 85.5
    test_score_low = 60.0

    sample_details_high = {
        "data": {
            "price": 150.25,
            "volume": 2_500_000_000,
            "rsi": 28.0,
            "ema20": 148.0,
            "ema50": 140.0,
            "bollinger_bands": {"upper": 160.0, "middle": 145.0, "lower": 130.0}
        },
        "sentiment": {
            "fgi_score": 20.0,
            "fgi_category": "Extreme Fear",
            "google_trends_interest": 75.0
        }
    }

    # Test signal alert
    print("\nAttempting to send a HIGH signal score alert (should send if URL is valid):")
    send_discord_alert(test_coin, test_score_high, sample_details_high)

    # Test price alert (assuming config.PRICE_ALERTS has targets set for 'solana')
    # To test, temporarily set a buy or sell target in config.py for 'solana'
    print("\nAttempting to send a PRICE alert (check config.py for targets):")
    check_price_alerts('solana', 139.50) # Simulate a price that triggers a buy alert

    # Test top detection alert
    print("\nAttempting to send a TOP DETECTION alert:")
    send_top_detection_alert('solana', 250.0, 85.0, 100.0, 2.5) # Simulate top detection conditions

    # Test dip buy alert
    print("\nAttempting to send a DIP BUY alert:")
    send_dip_buy_alert('sui', 3.0, 45.0, 3.2, 2.8, -15.0) # Simulate dip buy conditions

    # Test profit-taking alert (multiple targets)
    print("\nAttempting to send a PROFIT-TAKING alert (multiple targets):")
    # Simulate hitting the first target for Solana
    send_profit_taking_alert('solana', 280.50, 280.0, 20, 58.12885241)
    # Simulate hitting the second target for Solana
    send_profit_taking_alert('solana', 300.50, 300.0, 30, 58.12885241)

    # Test trailing stop alert - percent drop from ATH
    print("\nAttempting to send a TRAILING STOP alert (ATH Drop):")
    send_trailing_stop_alert('solana', 225.0, ath=300.0, drop_percent=25.0)

    # Test trailing stop alert - close below 50D EMA
    print("\nAttempting to send a TRAILING STOP alert (Close Below EMA50):")
    send_trailing_stop_alert('chainlink', 18.0, ema50=18.5, close_below_ema=True)

    print("\n--- Test complete ---")
