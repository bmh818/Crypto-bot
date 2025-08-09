import json
import os

# Define the file where the agent's state will be saved
STATE_FILE = "agent_state.json"

# Initialize global state variables (these will be loaded from file)
_last_observed_dynamic_ath = {}
_last_ema50_position = {}

def load_state():
    """
    Loads the agent's persistent state from the state file.
    """
    global _last_observed_dynamic_ath, _last_ema50_position
    
    if os.path.exists(STATE_FILE) and os.path.getsize(STATE_FILE) > 0:
        try:
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
                _last_observed_dynamic_ath = state.get('last_observed_dynamic_ath', {})
                _last_ema50_position = state.get('last_ema50_position', {})
            print(f"  Agent state loaded from {STATE_FILE}.")
        except json.JSONDecodeError as e:
            print(f"  Error loading agent state from {STATE_FILE}: {e}. Starting with empty state.")
            _last_observed_dynamic_ath = {}
            _last_ema50_position = {}
        except Exception as e:
            print(f"  An unexpected error occurred while loading state: {e}. Starting with empty state.")
            _last_observed_dynamic_ath = {}
            _last_ema50_position = {}
    else:
        print(f"  {STATE_FILE} not found or empty. Starting with empty state.")

def save_state():
    """
    Saves the agent's current persistent state to the state file.
    """
    state = {
        'last_observed_dynamic_ath': _last_observed_dynamic_ath,
        'last_ema50_position': _last_ema50_position
    }
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=4)
        print(f"  Agent state saved to {STATE_FILE}.")
    except Exception as e:
        print(f"  Error saving agent state to {STATE_FILE}: {e}")

def get_dynamic_ath(coin_id):
    """
    Returns the last observed dynamic ATH for a given coin.
    """
    return _last_observed_dynamic_ath.get(coin_id)

def set_dynamic_ath(coin_id, price):
    """
    Sets the last observed dynamic ATH for a given coin.
    """
    _last_observed_dynamic_ath[coin_id] = price

def get_ema50_position(coin_id):
    """
    Returns the last observed EMA50 position ('above' or 'below') for a given coin.
    """
    return _last_ema50_position.get(coin_id)

def set_ema50_position(coin_id, position):
    """
    Sets the last observed EMA50 position for a given coin.
    """
    _last_ema50_position[coin_id] = position

# Example usage (for testing purposes, not part of the main agent flow)
if __name__ == "__main__":
    print("--- Testing state_manager.py ---")

    # Simulate some state changes
    set_dynamic_ath('solana', 250.0)
    set_ema50_position('solana', 'above')
    set_dynamic_ath('chainlink', 20.0)
    set_ema50_position('chainlink', 'below')

    print(f"\nInitial state in memory (before save):")
    print(f"Solana ATH: {get_dynamic_ath('solana')}, EMA50 Pos: {get_ema50_position('solana')}")
    print(f"Chainlink ATH: {get_dynamic_ath('chainlink')}, EMA50 Pos: {get_ema50_position('chainlink')}")

    save_state() # Save to file

    # Reset in-memory state to simulate restart
    _last_observed_dynamic_ath = {}
    _last_ema50_position = {}
    print("\nState reset in memory (simulating restart).")
    print(f"Solana ATH: {get_dynamic_ath('solana')}, EMA50 Pos: {get_ema50_position('solana')}") # Should be None

    load_state() # Load from file

    print(f"\nState loaded from file:")
    print(f"Solana ATH: {get_dynamic_ath('solana')}, EMA50 Pos: {get_ema50_position('solana')}")
    print(f"Chainlink ATH: {get_dynamic_ath('chainlink')}, EMA50 Pos: {get_ema50_position('chainlink')}")

    print("\n--- Test complete ---")
