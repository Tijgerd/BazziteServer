#!/bin/bash

set -e

echo "-- Bazzite Integration Server Installer --"

# Ensure we are in the repo root
cd "$(dirname "$0")"

echo "Creating virtual environment"
python3 -m venv venv
source venv/bin/activate

echo "Installing Python dependencies"
pip install -r requirements.txt

echo "Setting up user systemd service"
mkdir -p ~/.config/systemd/user
cp systemd/bazzite-server.service.user ~/.config/systemd/user/bazzite-server.service

echo "Reloading user systemd daemon"
systemctl --user daemon-reload

echo "Enabling and starting service"
systemctl --user enable --now bazzite-server

echo "Done!"
echo "To check status: systemctl --user status bazzite-server"
echo "To see logs: journalctl --user -u bazzite-server -f"
