#!/bin/bash
# ═══════════════════════════════════════════════════
# SCEPTER MOMENTUM BOT v5.0 — DEPLOYMENT SCRIPT
# Run this on your VPS inside /root/momentum_bot/
# ═══════════════════════════════════════════════════

set -e

echo "════════════════════════════════════════════════"
echo "SCEPTER BOT v5.0 — DEPLOYING FIXES"
echo "════════════════════════════════════════════════"

cd /root/momentum_bot

# ───────────────────────────────────────
# STEP 1: Stop the bot if running
# ───────────────────────────────────────
echo ""
echo "[1/4] Stopping bot..."
pkill -f "python.*main.py" 2>/dev/null && echo "  Bot stopped" || echo "  Bot was not running"

# ───────────────────────────────────────
# STEP 2: Backup dead/unused files
# ───────────────────────────────────────
echo ""
echo "[2/4] Backing up dead files..."
mkdir -p backup

DEAD_FILES=(
    "fix_sl_tp_now.py"
    "fix_sl_tp_precision.py"
    "fix_sl_tp_simple.py"
    "emergency_sl_tp.py"
    "main_loop.py"
    "main_loop_fix.py"
    "main_verify.py"
    "margin_fix.py"
    "complete_trade_fix.py"
    "config_old.py"
    "config_relaxed.py"
    "swing_low_fix.py"
    "confirmation_strict.py"
    "trade_executor.py"
    "virtual_trade.py"
    "health.py"
    "live_trade.py"
    "test_mock.py"
    "margin_sizing.py"
)

for f in "${DEAD_FILES[@]}"; do
    if [ -f "$f" ]; then
        mv "$f" backup/
        echo "  Moved $f → backup/"
    fi
done

# ───────────────────────────────────────
# STEP 3: Backup current active files
# ───────────────────────────────────────
echo ""
echo "[3/4] Backing up current active files..."
mkdir -p backup/active_backup

ACTIVE_FILES=(
    "config.py"
    "confirmation.py"
    "trade_manager.py"
    "strategy.py"
    "main.py"
)

for f in "${ACTIVE_FILES[@]}"; do
    if [ -f "$f" ]; then
        cp "$f" "backup/active_backup/${f}.bak"
        echo "  Backed up $f"
    fi
done

# ───────────────────────────────────────
# STEP 4: Deploy fixed files
# ───────────────────────────────────────
echo ""
echo "[4/4] Deploying fixed files..."
echo "  ⏳ Waiting for you to paste the fixed files..."
echo ""
echo "════════════════════════════════════════════════"
echo "✅ BACKUP COMPLETE"
echo ""
echo "Now paste each fixed file using:"
echo "  cat > config.py << 'ENDOFFILE'"
echo "  [paste content]"
echo "  ENDOFFILE"
echo ""
echo "Repeat for: confirmation.py, trade_manager.py, strategy.py, main.py"
echo "════════════════════════════════════════════════"
