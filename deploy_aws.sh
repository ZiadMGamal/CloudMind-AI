#!/usr/bin/env bash
# ==============================================================================
# CloudMind AI — Automated 1-Command AWS EC2 (Ubuntu LTS) Deployment Script
# ==============================================================================
set -e

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CURRENT_USER="$(whoami)"

echo "============================================================"
echo " [1/5] Updating Ubuntu packages & installing Cloud tools..."
echo "============================================================"
sudo apt update -y
sudo apt install -y git curl wget net-tools apache2 sqlite3 python3 python3-pip python3-venv

echo "============================================================"
echo " [2/5] Setting up Python Virtual Environment & Libraries..."
echo "============================================================"
cd "$APP_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Initialize SQLite3 database (cloud.db)
python3 -c "from database import init_db; init_db(); print('SQLite3 cloud.db initialized successfully!')"

echo "============================================================"
echo " [3/5] Creating systemd background service (Gunicorn)..."
echo "============================================================"
sudo bash -c "cat > /etc/systemd/system/cloudmind.service <<EOF
[Unit]
Description=CloudMind AI Flask Web Application
After=network.target

[Service]
User=${CURRENT_USER}
WorkingDirectory=${APP_DIR}
Environment=\"PATH=${APP_DIR}/venv/bin\"
ExecStart=${APP_DIR}/venv/bin/gunicorn --workers 2 --bind 0.0.0.0:5000 app:app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF"

sudo systemctl daemon-reload
sudo systemctl enable cloudmind
sudo systemctl restart cloudmind

echo "============================================================"
echo " [4/5] Configuring Apache2 Reverse Proxy (Port 80 -> 5000)..."
echo "============================================================"
sudo a2enmod proxy proxy_http
sudo bash -c 'cat > /etc/apache2/sites-available/000-default.conf <<EOF
<VirtualHost *:80>
    ServerAdmin admin@cloudmind.local
    ProxyPreserveHost On
    ProxyPass / http://127.0.0.1:5000/
    ProxyPassReverse / http://127.0.0.1:5000/
    ErrorLog ${APACHE_LOG_DIR}/cloudmind_error.log
    CustomLog ${APACHE_LOG_DIR}/cloudmind_access.log combined
</VirtualHost>
EOF'

sudo systemctl enable apache2
sudo systemctl restart apache2

echo "============================================================"
echo " [5/5] Verifying Deployment & Fetching AWS Public IP..."
echo "============================================================"
PUBLIC_IP=$(curl -s --max-time 4 http://checkip.amazonaws.com || hostname -I | awk '{print $1}')

echo ""
echo "✅ CloudMind AI is LIVE on AWS EC2!"
echo "------------------------------------------------------------"
echo " 🌐 Public URL (Apache Port 80):  http://${PUBLIC_IP}"
echo " 🌐 Direct Gunicorn (Port 5000):  http://${PUBLIC_IP}:5000"
echo " 🗄️  SQLite3 Check Command:       sqlite3 \"${APP_DIR}/cloud.db\" \"SELECT id, server_node, severity FROM analysis_reports;\""
echo "------------------------------------------------------------"
