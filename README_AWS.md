# CloudMind AI — Smart Cloud Resource & Server Log Analyzer ☁️🤖

**CloudMind AI** is a cloud-native **AIOps (Artificial Intelligence for IT Operations)** web application built with **Python (Flask)**, **SQLite3 (`cloud.db`)**, **Pandas/NumPy**, and **Google Gemini AI**, designed for seamless deployment on **Amazon Web Services (AWS EC2 — Ubuntu Linux)** with **Apache2 Reverse Proxy** and **Gunicorn**.

---

## ✨ Key Features & Pages

1. **AWS Cloud Cluster Dashboard (`/`)**
   - Monitors the 3-Node Cloud Architecture (`VM1: Server`, `VM2: Client`, `VM3: Worker`) + NFS Shared Storage.
   - Reads real Ubuntu host telemetry (`uname -a`, `free -h`, `df -h`) when running on AWS EC2.
   - Interactive **Chart.js** visualizations and live VM load simulation backed by **SQLite3**.
2. **AI Log & Bottleneck Analyzer (`/analyzer`)**
   - Analyzes Ubuntu `syslog`, `Apache2` error logs, `NFS` timeouts, `SQLite` locks, OOM kills, and SSH brute-force logs.
   - Uses **Google Gemini LLM API** (if `GEMINI_API_KEY` is provided) with an automatic **Pandas/NumPy Statistical ML Fallback Engine** so it works **100% offline or without an API key**.
   - Outputs: **Severity Level**, **Multivariate Anomaly Score**, **Root Cause**, **AWS EC2/EBS Scaling Recommendation**, and **Ready-to-Run Ubuntu Terminal Commands**.
3. **SQLite3 Database Explorer & Audit History (`/history`)**
   - Full CRUD operations (`CREATE`, `SELECT`, `UPDATE`, `DELETE`) on `cloud.db`.
   - Search, filter by severity, update incident resolution status, inspect raw SQL queries, and export reports to **CSV** or **JSON**.

---

## 💻 Run Locally (Windows / macOS / Linux)

```bash
cd "The app/CloudMind AI"
pip install -r requirements.txt
python app.py
```

Open your browser at: **`http://127.0.0.1:5000`**

---

## 🚀 1-Command Deployment on AWS EC2 (Ubuntu 24.04 / 22.04 LTS)

### Step 1: Launch AWS EC2 Instance
1. Open **AWS Console -> EC2 -> Launch Instance**.
2. Name: `CloudMind-AI-Server` | OS: **Ubuntu Server 24.04 LTS** | Instance Type: `t2.micro` or `t3.micro` (Free Tier).
3. In **Security Group Inbound Rules**, allow:
   - **SSH** (`Port 22`) — `0.0.0.0/0`
   - **HTTP** (`Port 80`) — `0.0.0.0/0`
   - **Custom TCP** (`Port 5000`) — `0.0.0.0/0`

### Step 2: Connect & Deploy
Connect to your EC2 Ubuntu terminal (via **EC2 Instance Connect** or SSH) and run:

```bash
git clone https://github.com/YOUR_USERNAME/aws-cloudmind-ai.git
cd aws-cloudmind-ai
sed -i 's/\r$//' deploy_aws.sh
chmod +x deploy_aws.sh
./deploy_aws.sh
```

*(Optional: To enable live Google Gemini LLM responses in addition to the built-in ML engine, export `GEMINI_API_KEY="your_key"` or paste your key directly in the Analyzer UI).*

---

## 🗄️ Verify SQLite3 (`cloud.db`) via Ubuntu Terminal

```bash
sqlite3 cloud.db ".tables"
sqlite3 -header -column cloud.db "SELECT id, server_node, severity, anomaly_score, resolution_status FROM analysis_reports;"
```
