import json
import os
from datetime import datetime

# Import configuration settings
import config

def log_result(log_entry):
    """
    Saves a dictionary containing the results of a single coin check to a JSON log file.
    Ensures the log file is a valid JSON array and appends new entries.

    Args:
        log_entry (dict): A dictionary containing all the data for a single check,
                          including timestamp, coin, technical data, sentiment data,
                          signal score, and alert status.
    """
    log_file_path = config.LOG_FILE
    
    # Ensure the log file exists and is a valid JSON array
    if not os.path.exists(log_file_path) or os.path.getsize(log_file_path) == 0:
        # If file doesn't exist or is empty, initialize it with an empty JSON array
        with open(log_file_path, 'w') as f:
            json.dump([], f)
            
    try:
        # Read existing data
        with open(log_file_path, 'r+') as f:
            file_content = f.read()
            if not file_content: # Double-check in case of race condition or external modification
                data = []
            else:
                data = json.loads(file_content)
            
            # Append new entry
            data.append(log_entry)
            
            # Write updated data back to the file
            f.seek(0) # Rewind to the beginning of the file
            json.dump(data, f, indent=4) # Write with pretty-printing
            f.truncate() # Remove any remaining old content if the new content is shorter
        
        print(f"  Successfully logged data to {log_file_path}")

    except json.JSONDecodeError as e:
        print(f"  Error decoding JSON from {log_file_path}: {e}. File might be corrupted.")
        print("  Attempting to re-initialize the log file. Existing data might be lost.")
        # If the file is corrupted, try to re-initialize it
        with open(log_file_path, 'w') as f:
            json.dump([log_entry], f, indent=4) # Start a new log with the current entry
        print(f"  Re-initialized {log_file_path} with the current log entry.")
    except Exception as e:
        print(f"  An unexpected error occurred while logging to {log_file_path}: {e}")

# Example usage (for testing purposes, not part of the main agent flow)
if __name__ == "__main__":
    print("--- Testing logger.py ---")

    # Simulate a log entry
    sample_log_entry_1 = {
        "timestamp": datetime.now().isoformat(),
        "coin": "solana",
        "data": {
            "price": 150.25,
            "volume": 2_000_000_000,
            "rsi": 45.0,
            "ema20": 148.0,
            "ema50": 140.0,
            "bollinger_bands": {"upper": 160.0, "middle": 145.0, "lower": 130.0}
        },
        "sentiment": {
            "fgi_score": 55.0,
            "fgi_category": "Neutral",
            "google_trends_interest": 60.0
        },
        "signal_score": 72.5,
        "alert_sent": False
    }

    sample_log_entry_2 = {
        "timestamp": datetime.now().isoformat(),
        "coin": "chainlink",
        "data": {
            "price": 18.70,
            "volume": 500_000_000,
            "rsi": 32.0,
            "ema20": 19.0,
            "ema50": 20.0,
            "bollinger_bands": {"upper": 21.0, "middle": 19.5, "lower": 18.0}
        },
        "sentiment": {
            "fgi_score": 30.0,
            "fgi_category": "Fear",
            "google_trends_interest": 40.0
        },
        "signal_score": 85.1,
        "alert_sent": True
    }

    print("Logging first sample entry...")
    log_result(sample_log_entry_1)
    
    print("\nLogging second sample entry...")
    log_result(sample_log_entry_2)

    # Verify content
    try:
        with open(config.LOG_FILE, 'r') as f:
            logged_data = json.load(f)
            print(f"\nContent of {config.LOG_FILE} after logging:")
            print(json.dumps(logged_data, indent=4))
    except Exception as e:
        print(f"Error reading log file for verification: {e}")

    print("\n--- Test complete ---")
