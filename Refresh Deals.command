#!/bin/bash
# Double-click this file to refresh all cashback deals and the dashboard.

cd "$(dirname "$0")" || exit 1

echo "=============================================="
echo "  Deal Hunter - refreshing cashback data"
echo "=============================================="
echo

echo "[1/2] ShopBack (~2 minutes)..."
python3 scrape_shopback.py --no-canvas
sb_status=$?
echo

echo "[2/2] TopCashback (~1 minute)..."
python3 scrape_topcashback.py --no-canvas
tcb_status=$?
echo

echo "Rebuilding dashboard..."
python3 update_dashboard.py
python3 build_html.py
echo

if [[ $sb_status -eq 0 && $tcb_status -eq 0 ]]; then
    echo "All done! Open the dashboard in Cursor or data/*.csv for the results."
else
    echo "WARNING: one of the scrapers reported a problem - see output above."
fi
echo
read -r -p "Press Enter to close this window."
