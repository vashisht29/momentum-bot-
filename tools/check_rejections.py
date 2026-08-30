# check_rejections.py
# Parse bot.log and display a beautiful report of rejection reasons

import os
import re
from collections import Counter

LOG_FILE = "bot.log"

def analyze_rejections():
    if not os.path.exists(LOG_FILE):
        print(f"[ERROR] '{LOG_FILE}' not found in the current directory.")
        print("Please make sure you are running the bot with output redirected to bot.log:")
        print("Example: source venv/bin/activate && python3 main.py | tee -a bot.log")
        return

    print(f"Reading '{LOG_FILE}'...")
    
    rejections = []
    
    with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if "buy signal not confirmed" in line or "sell signal not confirmed" in line:
                if "Reason:" in line:
                    reason = line.split("Reason:")[1].strip()
                    rejections.append(reason)

    if not rejections:
        print("[INFO] No rejection reasons found in the log file yet.")
        return

    total = len(rejections)
    counter = Counter(rejections)
    
    print("\n" + "=" * 70)
    print("                 SCEPTER BOT REJECTION STATISTICS")
    print(f"                 Total Scan Rejections Analyzed: {total}")
    print("=" * 70)
    print(f" {'REJECTION REASON':<45} | {'COUNT':<6} | {'PERCENTAGE':<10}")
    print("-" * 70)
    
    for reason, count in counter.most_common():
        percentage = (count / total) * 100
        print(f" {reason:<45} | {count:<6} | {percentage:>8.2f}%")
        
    print("=" * 70 + "\n")

if __name__ == "__main__":
    analyze_rejections()
