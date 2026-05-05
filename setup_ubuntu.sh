#!/bin/bash
echo "Installing system dependencies..."
sudo apt update
sudo apt install -y python3-venv python3-pip nodejs npm

echo "Setting up Node.js dependencies..."
npm install

echo "Setting up Python virtual environment..."
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

echo "Setup complete! You can now run ./start_ubuntu.sh"
