import pandas as pd
import numpy as np
import sys
import os

# Get the path of the parent directory and add it to the system path
# This allows for importing modules from the main project directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from state_manager import get_dynamic_ath, set_dynamic_ath, get_ema50_position, set_ema50_position


def score_signal(data, sentiment, macro_trends, historical_data=None):
    """
    Combines technical indicators, social sentiment, and macro trends into a single score (0-100)
    using a configurable weighting system.

    The scoring logic is modular, transparent, and can be refined by adjusting weights in config.py.
    Higher scores (closer to 100) indicate a stronger bullish signal.
    Lower scores (closer to 0) indicate a stronger bearish signal.

    Args:
        data (dict): Dictionary containing technical indicator data from data_fetcher.py.
                     Expected keys: 'price', 'volume', 'rsi', 'ema20', 'ema50', 'ema200',
                     'bollinger_bands', 'price_change_7d_percent', 'price_change_30d_percent'.
        sentiment (dict): Dictionary containing sentiment data from sentiment_analyzer.py.
                          Expected keys: 'fgi_score', 'fgi_category', 'google_trends_interest'.
        macro_trends (dict): Dictionary containing macro trend data.
                             Expected keys: 'btc_current_price', 'btc_ath', 'eth_current_price', 'eth_ath', 'btc_dominance'.
        historical_data (pd.DataFrame): Optional. Historical price/volume data for dynamic volume scoring.

    Returns:
        float: A calculated signal score between 0 and 100.
    """
    # Start with a neutral score and get weights from the config file
    score = 50.0
    weights = config.SIGNAL_SCORING_WEIGHTS
    
    # --- Technical Indicator Scoring ---
    
    # 1. RSI (Relative Strength Index)
    # Score is adjusted based on how far RSI is from the neutral 50 mark.
    rsi = data.get('rsi')
    if rsi is not None:
        # Scale RSI score from -15 to +15
        # Example: RSI 30 -> 20 score, RSI 70 -> -20 score, scaled by weight
        if rsi <= 50:
            score += ((50 - rsi) * 0.5) * (weights['rsi'] * 100) / 25
        else:
            score -= ((rsi - 50) * 0.5) * (weights['rsi'] * 100) / 25
            
    # 2. EMA Crossover (20-period and 50-period EMA)
    ema20 = data.get('ema20')
    ema50 = data.get('ema50')
    if ema20 is not None and ema50 is not None:
        if ema20 > ema50:
            score += 15 * weights['ema_crossover'] # Bullish crossover
        elif ema20 < ema50:
            score -= 15 * weights['ema_crossover'] # Bearish crossover

    # 3. Price position relative to EMAs
    price = data.get('price')
    if price is not None and ema20 is not None and ema50 is not None:
        if price > ema20 and price > ema50:
            score += 10 * weights['ema_price_position'] # Price above both EMAs is bullish
        elif price < ema20 and price < ema50:
            score -= 10 * weights['ema_price_position'] # Price below both EMAs is bearish

    # 4. Bollinger Bands Position
    bb = data.get('bollinger_bands')
    if bb and bb.get('upper') is not None and bb.get('lower') is not None and price is not None:
        upper = bb['upper']
        lower = bb['lower']
        
        range_bb = upper - lower
        if range_bb > 0:
            dist_from_lower = (price - lower) / range_bb
            dist_from_upper = (upper - price) / range_bb

            if dist_from_lower < 0.1: # Price near or below lower band (oversold/dip)
                score += 15 * weights['bollinger_bands']
            elif dist_from_upper < 0.1: # Price near or above upper band (overbought)
                score -= 15 * weights['bollinger_bands']

    # 5. Dynamic Volume Spike
    # This requires historical data to be passed in, which we'll add to main.py later.
    # For now, we'll keep the simple check but include the logic for dynamic scoring.
    volume = data.get('volume')
    if volume is not None and historical_data is not None and 'volume' in historical_data.columns:
        # Calculate a 20-day simple moving average for volume
        volume_sma20 = historical_data['volume'].iloc[-20:].mean()
        if volume_sma20 > 0:
            if volume > (volume_sma20 * config.VOLUME_SPIKE_MULTIPLIER):
                score += 10 * weights['volume_spike'] # Strong volume, good signal
    else:
        # Fallback to the old simple volume check if historical data isn't provided
        if volume is not None and volume > 1_000_000_000:
            score += 5 * weights['volume_spike']

    # --- Sentiment Indicator Scoring ---

    # 6. Fear and Greed Index
    fgi_score = sentiment.get('fgi_score')
    if fgi_score is not None:
        if fgi_score <= 20: # Extreme Fear (contrarian bullish)
            score += 15 * weights['fgi_sentiment']
        elif fgi_score <= 40: # Fear (moderately contrarian bullish)
            score += 5 * weights['fgi_sentiment']
        elif fgi_score >= 80: # Extreme Greed (contrarian bearish)
            score -= 15 * weights['fgi_sentiment']
        elif fgi_score >= 60: # Greed (moderately contrarian bearish)
            score -= 5 * weights['fgi_sentiment']

    # 7. Google Trends Interest
    google_trends_interest = sentiment.get('google_trends_interest')
    if google_trends_interest is not None:
        if google_trends_interest >= 70: # High interest, can be bullish
            score += 10 * weights['google_trends']
        elif google_trends_interest >= 50: # Moderate interest
            score += 5 * weights['google_trends']
        elif google_trends_interest <= 30: # Low interest
            score -= 5 * weights['google_trends']

    # --- Macro Trend Scoring ---

    # 8. BTC/ETH All-Time High Proximity
    btc_price = macro_trends.get('btc_current_price')
    btc_ath = macro_trends.get('btc_ath')
    eth_price = macro_trends.get('eth_current_price')
    eth_ath = macro_trends.get('eth_ath')

    if btc_price is not None and btc_ath is not None and btc_ath > 0:
        btc_ath_proximity = (btc_price / btc_ath) * 100
        if btc_ath_proximity >= 98:
            score += 10 * weights['btc_eth_ath_proximity']
        elif btc_ath_proximity >= 90:
            score += 5 * weights['btc_eth_ath_proximity']

    if eth_price is not None and eth_ath is not None and eth_ath > 0:
        eth_ath_proximity = (eth_price / eth_ath) * 100
        if eth_ath_proximity >= 98:
            score += 10 * weights['btc_eth_ath_proximity']
        elif eth_ath_proximity >= 90:
            score += 5 * weights['btc_eth_ath_proximity']

    # 9. BTC Dominance (for Alt Season)
    btc_dominance = macro_trends.get('btc_dominance')
    if btc_dominance is not None:
        if btc_dominance < 50:
            score += 10 * weights['btc_dominance'] # Good for alts
        elif btc_dominance > 60:
            score -= 10 * weights['btc_dominance'] # Bad for alts
    
    # Ensure the score stays within 0-100 bounds
    final_score = max(0, min(100, score))

    print(f"  Calculated signal score: {final_score:.2f}")
    return final_score

def check_for_top_detection(data, sentiment):
    """
    Checks for conditions that indicate a potential market top for a coin,
    suggesting a profit-taking opportunity.

    Conditions:
    1. RSI (14) is very overbought (e.g., > 80).
    2. Price is significantly above 200-day EMA (e.g., > 50% above).
    3. A parabolic move is detected (e.g., very high 7-day and 30-day percentage gains).

    Args:
        data (dict): Dictionary containing technical indicator data.
                     Expected keys: 'price', 'rsi', 'ema200', 'price_change_7d_percent', 'price_change_30d_percent'.
        sentiment (dict): Dictionary containing sentiment data.
                          Expected keys: 'fgi_score'.

    Returns:
        tuple: (bool, float) - True if top detected, and a 'parabolic_factor' (e.g., 2.5x for 250% gain).
               Returns (False, 0.0) otherwise.
    """
    price = data.get('price')
    rsi = data.get('rsi')
    ema200 = data.get('ema200')
    price_change_7d = data.get('price_change_7d_percent')
    price_change_30d = data.get('price_change_30d_percent')

    # Condition 1: RSI very overbought
    is_rsi_overbought = rsi is not None and rsi > 80

    # Condition 2: Price significantly above 200D EMA
    is_above_ema200 = False
    if price is not None and ema200 is not None and ema200 > 0:
        # Price is at least 50% above 200D EMA
        is_above_ema200 = (price / ema200) >= 1.50 # 1.5x or 50% above

    # Condition 3: Parabolic move detected
    # This is a heuristic. A parabolic move often means very rapid, unsustainable gains.
    # We'll use a combination of high 7-day and 30-day gains.
    parabolic_factor = 0.0
    is_parabolic = False
    if price_change_7d is not None and price_change_30d is not None:
        # Example thresholds: 7-day gain > 50% AND 30-day gain > 100%
        if price_change_7d > 50 and price_change_30d > 100:
            is_parabolic = True
            # Calculate a factor based on how parabolic it is (e.g., average of 7d/30d gains as a multiplier)
            parabolic_factor = (price_change_7d + price_change_30d) / 200 # Divide by 100 for percentage, then by 2 for average

    # Additional factor: Extreme Greed in FGI can confirm a top
    is_fgi_extreme_greed = sentiment.get('fgi_score') is not None and sentiment.get('fgi_score') >= 80

    # Combine conditions for a 'top detection'
    # We require RSI overbought, price above 200D EMA, AND a parabolic move.
    # Extreme Greed FGI can be an additional confirming factor.
    
    if is_rsi_overbought and is_above_ema200 and is_parabolic:
        print(f"  Potential TOP detected: RSI ({rsi:.2f}), Price/EMA200 ({price/ema200:.2f}x), Parabolic ({price_change_7d:.2f}%/7d, {price_change_30d:.2f}%/30d).")
        # Add FGI as a strong confirmation, but not strictly required
        if is_fgi_extreme_greed:
            print("  Confirmed by Extreme Greed FGI.")
            return True, parabolic_factor
        return True, parabolic_factor

    return False, 0.0

def check_for_dip_buy(data, sentiment):
    """
    Checks for conditions that indicate a potential buying opportunity on a retracement or dip.

    Conditions:
    1. RSI (14) is oversold or near oversold (e.g., < 40).
    2. Price is near or below EMA20 and/or EMA50.
    3. Price is near the lower Bollinger Band.
    4. Recent negative price change (e.g., 7-day change is negative, but not too extreme).
    5. Market sentiment (FGI) is in "Fear" or "Extreme Fear."

    Args:
        data (dict): Dictionary containing technical indicator data.
                     Expected keys: 'price', 'rsi', 'ema20', 'ema50', 'bollinger_bands', 'price_change_7d_percent'.
        sentiment (dict): Dictionary containing sentiment data.
                          Expected keys: 'fgi_score'.

    Returns:
        bool: True if dip buy detected, False otherwise.
    """
    price = data.get('price')
    rsi = data.get('rsi')
    ema20 = data.get('ema20')
    ema50 = data.get('ema50')
    bb = data.get('bollinger_bands', {})
    bb_lower = bb.get('lower')
    price_change_7d = data.get('price_change_7d_percent')
    fgi_score = sentiment.get('fgi_score')

    # Condition 1: RSI oversold or near oversold
    is_rsi_oversold = rsi is not None and rsi < 40

    # Condition 2: Price near or below EMA20 and/or EMA50
    is_near_emas = False
    if price is not None and ema20 is not None and ema50 is not None:
        # Price is within 5% of EMA20 or EMA50, and below them
        if (price <= ema20 * 1.05 and price >= ema20 * 0.95) or \
           (price <= ema50 * 1.05 and price >= ema50 * 0.95):
            is_near_emas = True
        # Also consider price below both EMAs as a dip signal
        if price < ema20 and price < ema50:
            is_near_emas = True

    # Condition 3: Price near lower Bollinger Band
    is_near_bb_lower = False
    if price is not None and bb_lower is not None and bb_lower > 0:
        # Price is within 2% of the lower Bollinger Band
        if price <= bb_lower * 1.02:
            is_near_bb_lower = True

    # Condition 4: Recent negative price change (a dip, not a crash)
    # We want a dip, not a freefall. So, negative but not extremely negative.
    is_recent_dip = False
    if price_change_7d is not None and price_change_7d < 0 and price_change_7d > -20: # Negative but not more than -20% in 7 days
        is_recent_dip = True

    # Condition 5: Market sentiment is fearful (contrarian signal)
    is_fgi_fearful = fgi_score is not None and fgi_score <= 40

    # Combine conditions for a 'dip buy' detection
    # Require at least 3 of these conditions to be true for a strong signal
    
    conditions_met = 0
    if is_rsi_oversold: conditions_met += 1
    if is_near_emas: conditions_met += 1
    if is_near_bb_lower: conditions_met += 1
    if is_recent_dip: conditions_met += 1
    if is_fgi_fearful: conditions_met += 1

    if conditions_met >= 3:
        print(f"  Potential DIP BUY detected: RSI ({rsi:.2f}), Price/EMA20 ({price/ema20:.2f}x), BB Lower ({bb_lower:.2f}), 7D Change ({price_change_7d:.2f}%), FGI ({fgi_score:.1f}).")
        return True

    return False

def check_for_trailing_stop(coin_id, data, global_ath):
    """
    Checks for conditions that indicate a potential trailing stop exit.

    Conditions:
    1. Percentage Drop from a RECENT/DYNAMIC ATH (e.g., price drops X% from its highest observed price).
    2. Close Below 50D EMA (only if it was previously above).

    Args:
        coin_id (str): The CoinGecko ID of the cryptocurrency.
        data (dict): Dictionary containing technical indicator data.
                     Expected keys: 'price', 'ema50'.
        global_ath (float): The historical All-Time High price for the specific coin (from CoinGecko).

    Returns:
        tuple: (bool, str, float) - True if triggered, type of trigger, and relevant value (e.g., drop_percent or ema50).
               Returns (False, None, 0.0) otherwise.
    """
    price = data.get('price')
    ema50 = data.get('ema50')

    # Ensure we have essential data
    if price is None:
        return False, None, 0.0

    # --- Logic for Percentage Drop from Dynamic ATH ---
    percent_drop_threshold = config.TRAILING_STOP_ALERTS.get(coin_id, {}).get('percent_drop_from_ath')
    if percent_drop_threshold is not None:
        # Get dynamic ATH from state manager
        current_dynamic_ath_for_coin = get_dynamic_ath(coin_id)
        
        # Initialize dynamic ATH if not set, or if current price is higher than recorded dynamic ATH
        if current_dynamic_ath_for_coin is None:
            # If no dynamic ATH recorded, initialize it to the current price
            # This ensures we only track drops from prices observed *during this run or subsequent runs*
            current_dynamic_ath_for_coin = price
            if current_dynamic_ath_for_coin is None: # If price itself is None, cannot proceed
                return False, None, 0.0
            set_dynamic_ath(coin_id, current_dynamic_ath_for_coin) # Store initial dynamic ATH
        
        # If current price is higher than last observed dynamic ATH, update it.
        # Don't trigger alert immediately on new high, wait for drop.
        if price > current_dynamic_ath_for_coin:
            set_dynamic_ath(coin_id, price) # Update to new higher price
            print(f"  {coin_id.replace('-', ' ').title()} recorded new dynamic ATH: ${price:,.2f}")
            # Do not trigger alert here, as it's a new high, not a drop
        elif current_dynamic_ath_for_coin > 0: # Only check for drop if dynamic ATH is valid
            current_drop_percent = ((current_dynamic_ath_for_coin - price) / current_dynamic_ath_for_coin) * 100
            
            # Trigger if the drop is at or beyond the threshold
            if current_drop_percent >= percent_drop_threshold:
                print(f"  Trailing Stop (ATH Drop) detected: {current_drop_percent:.2f}% drop from dynamic ATH {current_dynamic_ath_for_coin:.2f}.")
                return True, "ATH_DROP", current_drop_percent

    # --- Logic for Close Below 50D EMA ---
    close_below_ema_enabled = config.TRAILING_STOP_ALERTS.get(coin_id, {}).get('close_below_50d_ema')
    if close_below_ema_enabled and ema50 is not None:
        current_ema_position = 'above' if price >= ema50 else 'below'
        previous_ema_position = get_ema50_position(coin_id) # Get previous position from state manager

        # Only trigger if it was previously 'above' and now 'below'
        if previous_ema_position == 'above' and current_ema_position == 'below':
            print(f"  Trailing Stop (Close Below EMA50) detected: Price {price:.2f} crossed below EMA50 {ema50:.2f}.")
            # Update position AFTER checking condition to ensure it's a cross
            set_ema50_position(coin_id, current_ema_position)
            return True, "CLOSE_BELOW_EMA50", ema50
        
        # Always update the last position for the next check
        set_ema50_position(coin_id, current_ema_position)


    return False, None, 0.0

# Example usage (for testing purposes, not part of the main agent flow)
if __name__ == "__main__":
    print("--- Testing signal_scoring.py with Top Detection, Dip Buy, and Trailing Stop ---")

    # Simulate data, sentiment for a TOP detection scenario
    sample_data_top = {
        "price": 250.0,
        "volume": 5_000_000_000,
        "rsi": 88.0, # Very overbought
        "ema20": 220.0,
        "ema50": 180.0,
        "ema200": 100.0, # Price is 2.5x 200D EMA
        "bollinger_bands": {"upper": 240.0, "middle": 200.0, "lower": 160.0},
        "price_change_7d_percent": 60.0, # High 7-day gain
        "price_change_30d_percent": 120.0 # High 30-day gain
    }
    sample_sentiment_top = {
        "fgi_score": 85.0, # Extreme Greed
        "fgi_category": "Extreme Greed",
        "google_trends_interest": 90.0
    }
    sample_macro_trends = {
        "btc_current_price": 70000.0,
        "btc_ath": 72000.0,
        "eth_current_price": 4000.0,
        "eth_ath": 4100.0,
        "btc_dominance": 48.0
    }

    # Test top detection
    is_top, parabolic_factor = check_for_top_detection(sample_data_top, sample_sentiment_top)
    print(f"\nTop Detected: {is_top}, Parabolic Factor: {parabolic_factor:.2f}")

    # Test signal scoring with top detection data
    signal_score_with_top = score_signal(sample_data_top, sample_sentiment_top, sample_macro_trends)
    print(f"Signal Score with Top Detection Data: {signal_score_with_top:.2f}")

    # Simulate data, sentiment for a DIP BUY scenario
    sample_data_dip = {
        "price": 120.0,
        "volume": 800_000_000,
        "rsi": 32.0, # Oversold
        "ema20": 125.0, # Price below EMA20
        "ema50": 130.0, # Price below EMA50
        "ema200": 150.0,
        "bollinger_bands": {"upper": 140.0, "middle": 130.0, "lower": 122.0}, # Price near lower BB
        "price_change_7d_percent": -12.0, # Recent dip
        "price_change_30d_percent": -25.0
    }
    sample_sentiment_dip = {
        "fgi_score": 35.0, # Fear
        "fgi_category": "Fear",
        "google_trends_interest": 50.0
    }

    # Test dip buy detection
    is_dip_buy = check_for_dip_buy(sample_data_dip, sample_sentiment_dip)
    print(f"\nDip Buy Detected: {is_dip_buy}")

    # --- Testing Trailing Stop (Dynamic ATH Logic) ---
    print("\n--- Testing Trailing Stop (Dynamic ATH Logic) ---")
    # Reset state manager's internal state for clean testing
    # Note: In actual run, state is loaded/saved from file.
    # We need to mock the state manager functions for isolated testing of this file
    class MockStateManager:
        _dynamic_aths = {}
        _ema_positions = {}
        def get_dynamic_ath(self, coin_id): return self._dynamic_aths.get(coin_id)
        def set_dynamic_ath(self, coin_id, price): self._dynamic_aths[coin_id] = price
        def get_ema50_position(self, coin_id): return self._ema_positions.get(coin_id)
        def set_ema50_position(self, coin_id, position): self._ema_positions[coin_id] = position
    
    _mock_state_manager = MockStateManager()
    # Temporarily replace imported functions with mock versions for testing
    get_dynamic_ath = _mock_state_manager.get_dynamic_ath
    set_dynamic_ath = _mock_state_manager.set_dynamic_ath
    get_ema50_position = _mock_state_manager.get_ema50_position
    set_ema50_position = _mock_state_manager.set_ema50_position


    # Mock config for this specific test
    class MockConfigForTS:
        TRAILING_STOP_ALERTS = {
            'solana': {
                'percent_drop_from_ath': 25.0, # 25% drop from ATH
                'close_below_50d_ema': False
            },
            'chainlink': {
                'percent_drop_from_ath': None,
                'close_below_50d_ema': True
            }
        }
    sys.modules['config'] = MockConfigForTS() # Temporarily replace config with mock for testing this file

    # Scenario 1: Initializing dynamic ATH (price below global ATH, no alert expected)
    # Should initialize dynamic ATH to global ATH, no alert.
    print("\nScenario 1: Initializing dynamic ATH (price below global ATH, no alert expected)")
    data_scenario1 = {"price": 250.0, "ema50": 200.0}
    is_ts1, type1, val1 = check_for_trailing_stop('solana', data_scenario1, global_ath=300.0)
    print(f"Result: {is_ts1}, {type1}, {val1:.2f} | Dynamic ATH: {get_dynamic_ath('solana')}")
    # Expected: False, None, 0.0 | Dynamic ATH: 300.0

    # Scenario 2: Price goes higher than initial dynamic ATH
    # Should update dynamic ATH, no alert.
    print("\nScenario 2: Price increases, updating dynamic ATH (no alert expected)")
    data_scenario2 = {"price": 270.0, "ema50": 210.0}
    is_ts2, type2, val2 = check_for_trailing_stop('solana', data_scenario2, global_ath=300.0)
    print(f"Result: {is_ts2}, {type2}, {val2:.2f} | Dynamic ATH: {get_dynamic_ath('solana')}")
    # Expected: False, None, 0.0 | Dynamic ATH: 270.0

    # Scenario 3: Price drops 25% from the new dynamic ATH (270 * 0.75 = 202.5)
    # Should trigger ATH_DROP alert.
    print("\nScenario 3: Price drops 25% from dynamic ATH (ATH_DROP alert expected)")
    data_scenario3 = {"price": 200.0, "ema50": 190.0} # 200.0 is a drop from 270.0
    is_ts3, type3, val3 = check_for_trailing_stop('solana', data_scenario3, global_ath=300.0)
    print(f"Result: {is_ts3}, {type3}, {val3:.2f} | Dynamic ATH: {get_dynamic_ath('solana')}")
    # Expected: True, ATH_DROP, ~25.9% (if 200 from 270)

    # --- Testing Trailing Stop (Close Below EMA50 - Reversal Logic) ---
    print("\n--- Testing Trailing Stop (Close Below EMA50 - Reversal Logic) ---")
    # Scenario 1: Price starts below EMA50 (no alert)
    print("\nScenario 1: Price starts below EMA50 (no alert expected)")
    data_ema_s1 = {"price": 17.0, "ema50": 18.0}
    is_ts_ema_s1, type_ema_s1, val_ema_s1 = check_for_trailing_stop('chainlink', data_ema_s1, global_ath=None)
    print(f"Result: {is_ts_ema_s1}, {type_ema_s1}, {val_ema_s1:.2f} | EMA Position: {get_ema50_position('chainlink')}")
    # Expected: False, None, 0.0 | EMA Position: below

    # Scenario 2: Price moves above EMA50 (no alert)
    print("\nScenario 2: Price moves above EMA50 (no alert expected)")
    data_ema_s2 = {"price": 19.0, "ema50": 18.0}
    is_ts_ema_s2, type_ema_s2, val_ema_s2 = check_for_trailing_stop('chainlink', data_ema_s2, global_ath=None)
    print(f"Result: {is_ts_ema_s2}, {type_ema_s2}, {val_ema_s2:.2f} | EMA Position: {get_ema50_position('chainlink')}")
    # Expected: False, None, 0.0 | EMA Position: above

    # Scenario 3: Price crosses below EMA50 (ALERT expected!)
    print("\nScenario 3: Price crosses BELOW EMA50 (ALERT expected!)")
    data_ema_s3 = {"price": 17.5, "ema50": 18.0}
    is_ts_ema_s3, type_ema_s3, val_ema_s3 = check_for_trailing_stop('chainlink', data_ema_s3, global_ath=None)
    print(f"Result: {is_ts_ema_s3}, {type_ema_s3}, {val_ema_s3:.2f} | EMA Position: {get_ema50_position('chainlink')}")
    # Expected: True, CLOSE_BELOW_EMA50, 18.0 | EMA Position: below

    # Scenario 4: Price remains below EMA50 (no further alert due to cooldown, but logic won't trigger)
    print("\nScenario 4: Price remains below EMA50 (no alert expected)")
    data_ema_s4 = {"price": 17.0, "ema50": 18.0}
    is_ts_ema_s4, type_ema_s4, val_ema_s4 = check_for_trailing_stop('chainlink', data_ema_s4, global_ath=None)
    print(f"Result: {is_ts_ema_s4}, {type_ema_s4}, {val_ema_s4:.2f} | EMA Position: {get_ema50_position('chainlink')}")
    # Expected: False, None, 0.0 | EMA Position: below

    print("\n--- Test complete ---")
