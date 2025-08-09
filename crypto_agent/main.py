import time
import json
import threading
from datetime import datetime
import os
import sys
sys.path.append(os.path.dirname(__file__))

# Import your configuration settings
import config

# Import functions from the newly created modules
from data_fetcher import fetch_data, get_current_price, get_coin_ath, get_btc_dominance_calculated, _get_coingecko_data
from sentiment_analyzer import analyze_sentiment
from signal_scoring import score_signal, check_for_top_detection, check_for_dip_buy, check_for_trailing_stop
from logger import log_result
from discord_alert import send_discord_alert, check_price_alerts, send_top_detection_alert, send_dip_buy_alert, send_profit_taking_alert, send_trailing_stop_alert
from portfolio_tracker import track_portfolio_performance, send_portfolio_alert
from summary_report import send_daily_summary_report
from state_manager import load_state, save_state

# Global variable to store the latest fetched prices for the fast loop
latest_prices = {}

def run_signal_analysis_loop():
    """
    Runs the comprehensive signal analysis and portfolio tracking for all tracked coins.
    This loop runs less frequently (e.g., every 6 hours).
    """
    global latest_prices
    
    while True:
        current_time = datetime.now()
        print(f"\n--- Running comprehensive signal analysis & portfolio check at {current_time.strftime('%Y-%m-%d %H:%M:%S')} ---")

        # --- Fetch Macro Trends (once per comprehensive run) ---
        print("\nFetching Macro Trends...")
        btc_current_price = get_current_price('bitcoin')
        btc_ath = get_coin_ath('bitcoin')
        eth_current_price = get_current_price('ethereum')
        eth_ath = get_coin_ath('ethereum')
        btc_dominance = get_btc_dominance_calculated()

        macro_trends_data = {
            'btc_current_price': btc_current_price,
            'btc_ath': btc_ath,
            'eth_current_price': eth_current_price,
            'eth_ath': eth_ath,
            'btc_dominance': btc_dominance
        }
        print("Macro Trend fetching complete.")

        for coin in config.TRACKED_COINS:
            print(f"\nProcessing {coin.replace('-', ' ').title()} (Comprehensive Analysis)...")
            signal_alert_sent_for_this_run = False
            top_detection_alert_sent_for_this_run = False
            dip_buy_alert_sent_for_this_run = False
            profit_taking_alert_sent_for_this_run = False
            trailing_stop_alert_sent_for_this_run = False
            
            try:
                # Step 1: Fetch comprehensive data and compute technical indicators
                # We now get the raw historical data to use for dynamic volume scoring
                historical_data = _get_coingecko_data(coin, days=250)
                coin_data = fetch_data(coin)
                current_price = coin_data.get('price')
                coin_ath_historical = get_coin_ath(coin)

                if current_price is None:
                    print(f"  Skipping comprehensive analysis for {coin} due to insufficient data from data_fetcher (price missing).")
                    continue

                latest_prices[coin] = current_price
                coin_sentiment = analyze_sentiment(coin)

                # Step 2: Check for Top Detection
                is_top_detected, parabolic_factor = check_for_top_detection(coin_data, coin_sentiment)
                if is_top_detected:
                    top_detection_alert_sent_for_this_run = send_top_detection_alert(
                        coin, current_price, coin_data.get('rsi'), coin_data.get('ema200'), parabolic_factor
                    )

                # Step 3: Check for Dip Buy
                is_dip_buy = check_for_dip_buy(coin_data, coin_sentiment)
                if is_dip_buy:
                    dip_buy_alert_sent_for_this_run = send_dip_buy_alert(
                        coin, current_price, coin_data.get('rsi'), coin_data.get('ema20'), 
                        coin_data.get('bollinger_bands', {}).get('lower'), coin_data.get('price_change_7d_percent')
                    )

                # Step 4: Check for Profit-Taking Alerts
                profit_taking_targets_list = config.PROFIT_TAKING_ALERTS.get(coin, [])
                if profit_taking_targets_list:
                    current_holdings_quantity = config.PORTFOLIO_HOLDINGS.get(coin, {}).get('quantity', 0.0)
                    if current_holdings_quantity > 0:
                        for target in profit_taking_targets_list:
                            target_price = target.get('target_price')
                            sell_percentage = target.get('sell_percentage')

                            if target_price is not None and sell_percentage is not None and current_price >= target_price:
                                if send_profit_taking_alert(coin, current_price, target_price, sell_percentage, current_holdings_quantity):
                                    profit_taking_alert_sent_for_this_run = True
                    else:
                        print(f"  Profit-taking targets configured for {coin}, but quantity is 0 in PORTFOLIO_HOLDINGS. Skipping alerts.")

                # Step 5: Check for Trailing Stop Alerts
                is_trailing_stop, stop_type, value = check_for_trailing_stop(coin, coin_data, coin_ath_historical)
                if is_trailing_stop:
                    if stop_type == "ATH_DROP":
                        trailing_stop_alert_sent_for_this_run = send_trailing_stop_alert(
                            coin, current_price, ath=coin_ath_historical, drop_percent=value
                        )
                    elif stop_type == "CLOSE_BELOW_EMA50":
                        trailing_stop_alert_sent_for_this_run = send_trailing_stop_alert(
                            coin, current_price, ema50=value, close_below_ema=True
                        )
                
                # Step 6: Combine all into a single signal score, including macro trends and historical data for dynamic volume
                signal_score = score_signal(coin_data, coin_sentiment, macro_trends_data, historical_data=historical_data)
                
                # Step 7: Send Signal Alerts
                if signal_score >= config.ALERT_SCORE_THRESHOLD:
                    signal_alert_sent_for_this_run = send_discord_alert(coin, signal_score, {"data": coin_data, "sentiment": coin_sentiment})
                else:
                    print(f"  Signal for {coin.replace('-', ' ').title()} (score: {signal_score:.2f}) not strong enough for alert.")

                # Prepare log entry for comprehensive run
                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "coin": coin,
                    "data": coin_data,
                    "sentiment": coin_sentiment,
                    "macro_trends": macro_trends_data,
                    "signal_score": signal_score,
                    "signal_alert_sent": signal_alert_sent_for_this_run,
                    "price_alert_sent": False,
                    "top_detection_alert_sent": top_detection_alert_sent_for_this_run,
                    "dip_buy_alert_sent": dip_buy_alert_sent_for_this_run,
                    "profit_taking_alert_sent": profit_taking_alert_sent_for_this_run,
                    "trailing_stop_alert_sent": trailing_stop_alert_sent_for_this_run
                }

                # Step 8: Log every comprehensive check
                log_result(log_entry)

            except Exception as e:
                print(f"  An error occurred during comprehensive analysis for {coin.replace('-', ' ').title()}: {e}")
        
        # --- Portfolio Tracking & Alerts (after all coins are processed in the slow loop) ---
        portfolio_summary = track_portfolio_performance()
        if portfolio_summary:
            send_portfolio_alert(portfolio_summary)
        
        # NEW: Save the agent's state after each comprehensive run
        save_state()

        print(f"\n--- Comprehensive check complete. Sleeping for {config.RUN_EVERY_HOURS} hours ---")
        time.sleep(config.RUN_EVERY_HOURS * 3600)

def run_price_monitoring_loop():
    """
    Runs a fast loop for real-time price monitoring and alerts.
    This loop runs much more frequently (e.g., every 1-5 minutes).
    """
    global latest_prices
    price_check_interval_seconds = config.PRICE_CHECK_INTERVAL_SECONDS

    while True:
        for coin in config.TRACKED_COINS:
            fetched_price = get_current_price(coin)
            if fetched_price is not None:
                latest_prices[coin] = fetched_price
                check_price_alerts(coin, fetched_price)
            else:
                print(f"  Could not fetch current price for {coin} in fast loop.")
        
        send_daily_summary_report()
        time.sleep(price_check_interval_seconds)

def main():
    """
    Main function to start both the comprehensive signal analysis loop
    and the fast price monitoring loop concurrently.
    """
    print("Crypto Intelligence Agent Started! 🚀")
    # NEW: Load the agent's state at startup
    load_state()

    print(f"Monitoring coins: {', '.join(config.TRACKED_COINS)}")
    print(f"Comprehensive signal analysis runs every {config.RUN_EVERY_HOURS} hours.")
    print(f"Price monitoring runs every {config.PRICE_CHECK_INTERVAL_SECONDS // 60} minute(s).")
    print(f"Signal Alert threshold: {config.ALERT_SCORE_THRESHOLD}")
    print(f"Signal Alert cooldown per coin: {config.ALERT_COOLDOWN_HOURS} hours.")
    print(f"Price Alert cooldown per coin: {config.PRICE_ALERT_COOLDOWN_HOURS} hours.")
    print(f"Portfolio Alert cooldown: {config.PORTFOLIO_ALERT_COOLDOWN_HOURS} hours.")
    print(f"Daily Summary Report time: {config.SUMMARY_REPORT_TIME} UTC.")
    print(f"Profit-Taking Alert cooldown: {config.PROFIT_TAKING_ALERT_COOLDOWN_HOURS} hours.")
    print(f"Trailing Stop Alert cooldown: {config.TRAILING_STOP_ALERT_COOLDOWN_HOURS} hours.")
    print(f"Logs will be saved to: {config.LOG_FILE}")
    print("\nMacro Trend analysis includes BTC/ETH ATH and BTC Dominance.")

    # Start the comprehensive signal analysis loop in a separate thread
    signal_thread = threading.Thread(target=run_signal_analysis_loop)
    signal_thread.daemon = True
    signal_thread.start()

    # Start the fast price monitoring loop in a separate thread
    price_thread = threading.Thread(target=run_price_monitoring_loop)
    price_thread.daemon = True
    price_thread.start()

    while True:
        time.sleep(1)

if __name__ == "__main__":
    main()
