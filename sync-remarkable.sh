#!/bin/bash
# Automated reMarkable sync script
# Syncs reMarkable notes to ~/Documents/reMarkable as PDFs

set -euo pipefail

RMIRRO_DIR="$HOME/20-DEV/_PYTHON/10-PERSO/rmirro"
OUTPUT_DIR="$HOME/Documents/reMarkable"
LOG_FILE="$HOME/Library/Logs/remarkable-sync.log"
VENV_PYTHON="$RMIRRO_DIR/.venv/bin/python"
export DYLD_LIBRARY_PATH="/opt/homebrew/opt/cairo/lib"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# Check if reMarkable is reachable via SSH
if ! ssh -o ConnectTimeout=3 remarkable "true" 2>/dev/null; then
    log "reMarkable not reachable, skipping sync"
    exit 0
fi

log "Starting reMarkable sync"

cd "$OUTPUT_DIR"

# Run rmirro with auto-confirm
"$VENV_PYTHON" "$RMIRRO_DIR/rmirro.py" remarkable \
    -r render_rmc.py \
    --yes \
    2>&1 | tee -a "$LOG_FILE"

log "Sync complete"
