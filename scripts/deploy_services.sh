#!/usr/bin/env bash
set -e

# Copy services
sudo cp systemd/hanna.service /etc/systemd/system/
sudo cp systemd/hanna-toolsync.service /etc/systemd/system/

# Reload and Enable
sudo systemctl daemon-reload
sudo systemctl enable hanna-toolsync.service
sudo systemctl enable hanna.service

echo "[OK] HANNA Systemd Unit config deployed. Use 'sudo systemctl start hanna.service' to launch."
