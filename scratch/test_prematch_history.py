import json
import os
import datetime

HISTORY_FILE = "data/prematch_history.json"

def test():
    # Load history if exists
    history = {}
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
    print(f"Current history entries: {len(history)}")

if __name__ == "__main__":
    test()
