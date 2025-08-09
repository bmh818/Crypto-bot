# config.py

# --- CORE AGENT SETTINGS ---
# Coins to track (CoinGecko IDs)
TRACKED_COINS = ['solana', 'chainlink', 'sui', 'sei-network']

# Time between runs (in hours)
RUN_EVERY_HOURS = 6  # Options: 6, 12, 24 — change as needed

# Discord Webhook URL
DISCORD_WEBHOOK_URL = "https://discordapp.com/api/webhooks/1402421996511428688/jRKcMV0zjJaCQQItl3zu3FLLGWeO0MBFvRPcitCD0XjIQc8ExZpcyiqGoAw-TDsX_1xc"

# Alert score threshold (0–100)
ALERT_SCORE_THRESHOLD = 80  # Only send signal alert if score is high enough

# Cooldown between signal alerts per coin (in hours)
ALERT_COOLDOWN_HOURS = 6

# Logging
LOG_FILE = "signal_logs.json"


# --- SIGNAL SCORING SETTINGS ---
# Define the weights for each factor in the signal score.
# Weights must be a float between 0.0 and 1.0.
# The total sum of all weights should ideally be 1.0.
SIGNAL_SCORING_WEIGHTS = {
    'rsi': 0.15,
    'ema_crossover': 0.20,
    'ema_price_position': 0.20,
    'bollinger_bands': 0.10,
    'volume_spike': 0.10,
    'fgi_sentiment': 0.10,
    'google_trends': 0.05,
    'btc_eth_ath_proximity': 0.05,
    'btc_dominance': 0.05,
}

# Define multiplier for a strong volume spike
# A volume spike is defined as a volume greater than this multiple of the 20-day average.
VOLUME_SPIKE_MULTIPLIER = 1.5


# --- GENERAL PRICE ALERT SETTINGS ---
# Define specific price targets for general buy or sell alerts.
# Set to None if you don't want an alert for that price type.
# Example: "solana": {"buy": 140.0, "sell": 160.0}
# Meaning: Alert if Solana drops to 140 or rises to 160.
PRICE_ALERTS = {
    'solana': {
        'buy': 130,
        'sell': 230
    },
    'chainlink': {
        'buy': 13,
        'sell': 25
    },
    'sui': {
        'buy': 2.5,
        'sell': 5
    },
    'sei-network': {
        'buy': .2,
        'sell': .5
    }
    # Add more coins here if needed, matching their CoinGecko ID
}

# Cooldown between general price alerts per coin (in hours)
# This prevents spamming if the price hovers around your target.
PRICE_ALERT_COOLDOWN_HOURS = 6

# How often the fast price monitoring loop runs (in seconds)
PRICE_CHECK_INTERVAL_SECONDS = 60 # Check every 60 seconds (1 minute)


# --- PORTFOLIO TRACKING SETTINGS ---
# Define your cryptocurrency holdings for tracking.
# Use CoinGecko IDs for 'coin_id'.
# 'quantity': The number of coins you hold.
# The agent will calculate daily performance (change from 24 hours ago).
PORTFOLIO_HOLDINGS = {
    'solana': {
        'quantity': 58.12885241
    },
    'chainlink': {
        'quantity': 443.13286966
    },
    'sui': {
        'quantity': 575.98751
    },
    'sei-network': {
        'quantity': 7168.87
    }
    # Add more coins here if needed, matching their CoinGecko ID
}

# Thresholds for portfolio alerts (in percentage change)
# Set to None if you don't want alerts for this type.
# These will now refer to daily percentage changes.
PORTFOLIO_ALERT_THRESHOLDS = {
    'total_portfolio_percent_change': 10,
    'individual_coin_percent_change': 10
}

# Cooldown for portfolio alerts (in hours)
PORTFOLIO_ALERT_COOLDOWN_HOURS = 12


# --- DAILY SUMMARY REPORT SETTINGS ---
# Time to send the daily summary report (in 24-hour format, e.g., "22:00" for 10 PM)
# Set to None to disable the daily summary report.
SUMMARY_REPORT_TIME = "22:00" # 10 PM


# --- PROFIT-TAKING ALERT SETTINGS ---
# Define multiple specific price targets for profit-taking recommendations.
# Each target is a dictionary with 'target_price' and 'sell_percentage'.
# Example: [{'target_price': 280.0, 'sell_percentage': 20}, {'target_price': 300.0, 'sell_percentage': 30}]
# Set to an empty list [] if you don't want this type of alert for a coin.
PROFIT_TAKING_ALERTS = {
    'solana': [ # Example: [{'target_price': 280.0, 'sell_percentage': 20}]
        {'target_price': 295.0, 'sell_percentage': 20},
        {'target_price': 340.0, 'sell_percentage': 30},
        {'target_price': 445.0, 'sell_percentage': 20}],
    'chainlink': [        
        {'target_price': 27.0, 'sell_percentage': 20},
        {'target_price': 47.0, 'sell_percentage': 30},
        {'target_price': 75.0, 'sell_percentage': 20}],
    'sui': [       
        {'target_price': 4.8, 'sell_percentage': 20},
        {'target_price': 9.8, 'sell_percentage': 30},
        {'target_price': 19.5, 'sell_percentage': 20}],
    'sei-network': [        
        {'target_price': 0.95, 'sell_percentage': 20},
        {'target_price': 1.95, 'sell_percentage': 30},
        {'target_price': 3.95, 'sell_percentage': 20}]
    # Add more coins here if needed, matching their CoinGecko ID
}

# Cooldown for profit-taking alerts per coin and per target (in hours)
# This prevents spamming if the price hovers around a target.
PROFIT_TAKING_ALERT_COOLDOWN_HOURS = 24


# --- TRAILING STOP ALERT SETTINGS ---
# Define conditions for trailing stop alerts to protect gains or signal trend breakdown.
# Set to None to disable a specific type of trailing stop.
TRAILING_STOP_ALERTS = {
    'solana': {
        'percent_drop_from_ath': 20, # Example: 25.0 (Alert if price drops 25% from its All-Time High)
        'close_below_50d_ema': True   # Set to True to enable alert if price closes below 50-day EMA
    },
    'chainlink': {
        'percent_drop_from_ath': 20,
        'close_below_50d_ema': True
    },
    'sui': {
        'percent_drop_from_ath': 25,
        'close_below_50d_ema': True
    },
    'sei-network': {
        'percent_drop_from_ath': 30,
        'close_below_50d_ema': True
    }
    # Add more coins here if needed, matching their CoinGecko ID
}

# Cooldown for trailing stop alerts per coin (in hours)
TRAILING_STOP_ALERT_COOLDOWN_HOURS = 48 # Often a longer cooldown for these critical alerts