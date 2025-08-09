import requests
import json
import time
from datetime import datetime, timedelta
import config
from portfolio_tracker import track_portfolio_performance, get_coin_24h_change # Corrected import: added get_coin_24h_change
from data_fetcher import get_current_price # To get current prices for non-portfolio tracked coins
from sentiment_analyzer import analyze_sentiment # To get FGI for general market sentiment

# Dictionary to store the last time the daily summary was sent
last_summary_sent_date = None

def send_daily_summary_report():
    """
    Generates and sends a daily summary report to Discord.
    This report includes portfolio performance and a general market overview.
    """
    global last_summary_sent_date

    webhook_url = config.DISCORD_WEBHOOK_URL
    if not webhook_url or webhook_url == "YOUR_DISCORD_WEBHOOK_URL_HERE":
        print("  Discord Webhook URL not configured. Skipping daily summary report.")
        return False

    current_time = datetime.now()
    
    # Check if the summary has already been sent today
    if last_summary_sent_date and last_summary_sent_date.date() == current_time.date():
        # print("  Daily summary already sent today. Skipping.") # Too verbose for regular checks
        return False

    # Check if current time matches the configured summary time
    summary_hour, summary_minute = map(int, config.SUMMARY_REPORT_TIME.split(':'))
    
    # Send if current time is past the configured time AND it hasn't been sent today
    # To avoid sending multiple times if the agent restarts after the time
    if current_time.hour == summary_hour and current_time.minute >= summary_minute:
        if not last_summary_sent_date or last_summary_sent_date.date() < current_time.date():
            print(f"\n--- Generating daily summary report for {current_time.strftime('%Y-%m-%d')} ---")
            
            # --- Get Portfolio Performance ---
            portfolio_summary = track_portfolio_performance()
            
            # --- Get General Market Overview (FGI) ---
            market_sentiment = analyze_sentiment("bitcoin") # Use bitcoin as a proxy for general market FGI
            fgi_score = market_sentiment.get('fgi_score')
            fgi_category = market_sentiment.get('fgi_category')

            # --- Get Current Prices for All Tracked Coins (including those not in portfolio) ---
            all_tracked_coins_info = {}
            for coin_id in config.TRACKED_COINS:
                # Use get_coin_24h_change for tracked coins to get price and 24h change
                coin_data = get_coin_24h_change(coin_id) # Now correctly imported
                if coin_data:
                    all_tracked_coins_info[coin_id] = coin_data
                else:
                    print(f"  Could not get 24h change for {coin_id} for summary.")

            # --- Construct Discord Embed ---
            embed = {
                "title": f"☀️ Daily Crypto Summary: {current_time.strftime('%Y-%m-%d')} ☀️",
                "description": "Here's your end-of-day overview of the crypto market and your portfolio.",
                "color": 5793266, # A nice blue color
                "fields": [],
                "footer": {
                    "text": f"Report generated at {current_time.strftime('%Y-%m-%d %H:%M:%S')} UTC"
                }
            }

            # Add Portfolio Summary
            if portfolio_summary and portfolio_summary['total_value'] > 0:
                embed["fields"].append({
                    "name": "💰 Portfolio Overview",
                    "value": f"Total Value: **${portfolio_summary['total_value']:,.2f}**\n"
                             f"24h Change: **{portfolio_summary['total_change_24h_percent']:+.2f}%**",
                    "inline": False
                })
                
                # Add individual coin performance from portfolio
                if portfolio_summary['individual_coins']:
                    individual_perf_str = ""
                    for coin_id, data in portfolio_summary['individual_coins'].items():
                        individual_perf_str += (
                            f"**{coin_id.replace('-', ' ').title()}**: "
                            f"${data['current_price']:,.2f} ({data['daily_change_percent']:+.2f}%)\n"
                        )
                    embed["fields"].append({
                        "name": "Individual Holdings (24h Change)",
                        "value": individual_perf_str.strip(),
                        "inline": False
                    })
            else:
                embed["fields"].append({
                    "name": "💰 Portfolio Overview",
                    "value": "No portfolio holdings configured or data unavailable.",
                    "inline": False
                })

            # Add General Market Sentiment
            if fgi_score is not None:
                embed["fields"].append({
                    "name": "📊 Market Sentiment (FGI)",
                    "value": f"Score: **{fgi_score:.1f}** ({fgi_category})",
                    "inline": False
                })
            
            # Add Current Prices for All Tracked Coins (if not already covered by portfolio)
            other_tracked_coins_str = ""
            # Ensure portfolio_summary is not None before checking 'individual_coins'
            portfolio_coins = portfolio_summary['individual_coins'].keys() if portfolio_summary and 'individual_coins' in portfolio_summary else set()

            for coin_id, data in all_tracked_coins_info.items():
                if coin_id not in portfolio_coins: # Check if coin is NOT in portfolio
                    other_tracked_coins_str += (
                        f"**{coin_id.replace('-', ' ').title()}**: "
                        f"${data['price']:,.2f} ({data['price_change_24h']:+.2f}%)\n"
                    )
            if other_tracked_coins_str:
                embed["fields"].append({
                    "name": "📈 Other Tracked Coins (24h Change)",
                    "value": other_tracked_coins_str.strip(),
                    "inline": False
                })


            payload = {"embeds": [embed]}

            try:
                response = requests.post(webhook_url, json=payload, timeout=15)
                response.raise_for_status()
                print(f"  Daily summary report sent successfully.")
                last_summary_sent_date = current_time # Update global variable
                return True
            except requests.exceptions.RequestException as e:
                print(f"  Error sending daily summary report: {e}")
                return False
    return False

# Example usage (for testing purposes, not part of the main agent flow)
if __name__ == "__main__":
    print("--- Testing summary_report.py ---")

    # To test properly, ensure config.py has:
    # - DISCORD_WEBHOOK_URL set
    # - PORTFOLIO_HOLDINGS configured with quantities
    # - SUMMARY_REPORT_TIME set to a time close to now for testing (e.g., current hour and minute)
    
    # Temporarily set a test time for the summary report in config for immediate testing
    # config.SUMMARY_REPORT_TIME = datetime.now().strftime("%H:%M") 
    
    # Call the function directly
    send_daily_summary_report()

    print("\n--- Test complete ---")

