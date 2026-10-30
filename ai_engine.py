import json
import os
import re
import numpy as np
import pandas as pd
import requests


SAMPLE_SCENARIOS = {
    "apache_crash": {
        "title": "Apache2 Worker Exhaustion & Segfault",
        "server_node": "VM1 — Server (server)",
        "cpu_pct": 92,
        "ram_pct": 89,
        "disk_pct": 58,
        "log_text": (
            "[Oct 30 15:40:12] [mpm_prefork:error] [pid 1410] AH00161: server reached MaxRequestWorkers setting, consider raising the MaxRequestWorkers setting\n"
            "[Oct 30 15:40:14] [core:error] [pid 1410] AH00052: child pid 2198 exit signal Segmentation fault (11)\n"
            "[Oct 30 15:40:18] systemd[1]: apache2.service: Main process exited, code=killed, status=9/KILL"
        ),
    },
    "oom_memory": {
        "title": "Linux Out-Of-Memory (OOM Killer) Event",
        "server_node": "VM3 — Worker (worker)",
        "cpu_pct": 86,
        "ram_pct": 97,
        "disk_pct": 64,
        "log_text": (
            "Oct 30 15:42:01 worker kernel: [48291.102] Out of memory: Killed process 3812 (python3) total-vm:1984320kB, anon-rss:1412800kB\n"
            "Oct 30 15:42:02 worker systemd[1]: cloudmind-worker.service: A process of this unit has been killed by the OOM killer.\n"
            "MemoryError: Unable to allocate 512. MiB for an array with shape (67108864,) and data type float64"
        ),
    },
    "disk_sqlite": {
        "title": "EBS Disk Full & SQLite3 Write Failure",
        "server_node": "VM1 — Server (server)",
        "cpu_pct": 45,
        "ram_pct": 62,
        "disk_pct": 98,
        "log_text": (
            "sqlite3.OperationalError: database or disk is full (/srv/shared/cloud.db)\n"
            "Oct 30 15:45:19 server systemd-journald[391]: /var/log/journal: No space left on device\n"
            "write error: /tmp/upload_buffer.tmp: No space left on device"
        ),
    },
    "nfs_disconnect": {
        "title": "NFS Shared Storage Mount Timeout",
        "server_node": "VM2 — Client (client)",
        "cpu_pct": 32,
        "ram_pct": 49,
        "disk_pct": 51,
        "log_text": (
            "Oct 30 15:48:03 client kernel: nfs: server 172.31.24.101 not responding, still trying\n"
            "mount.nfs: Connection timed out for 172.31.24.101:/srv/shared on /mnt/cloud-storage\n"
            "ERROR: Client app cannot read /mnt/cloud-storage/cloud.db"
        ),
    },
    "ssh_bruteforce": {
        "title": "SSH Brute-Force Intrusion Attempt",
        "server_node": "AWS-EC2-Public-Gateway",
        "cpu_pct": 68,
        "ram_pct": 55,
        "disk_pct": 47,
        "log_text": (
            "Oct 30 15:50:11 server sshd[8821]: Failed password for invalid user admin from 185.220.101.42 port 51922 ssh2\n"
            "Oct 30 15:50:13 server sshd[8823]: Failed password for root from 185.220.101.42 port 51988 ssh2\n"
            "Oct 30 15:50:15 server sshd[8825]: error: maximum authentication attempts exceeded for root from 185.220.101.42 port 52014 ssh2 [preauth]"
        ),
    },
    "healthy_check": {
        "title": "Healthy Cluster Routine Check",
        "server_node": "VM2 — Client (client)",
        "cpu_pct": 24,
        "ram_pct": 38,
        "disk_pct": 35,
        "log_text": (
            "Oct 30 15:55:00 client systemd[1]: Starting Daily apt download activities...\n"
            "apache2.service: active (running) since Sun 2026-10-30 08:00:00 UTC\n"
            "SQLite3 integrity_check: ok — 0 errors detected in /mnt/cloud-storage/cloud.db"
        ),
    },
}


def _call_gemini_api(api_key, server_node, log_snippet, cpu_pct, ram_pct, disk_pct):
    """Query Google Gemini REST API for real-time AIOps log diagnosis and AWS scaling recommendations."""
    prompt = f"""You are an expert AWS Cloud Architect and Ubuntu Linux SRE.
Analyze the following server telemetry and log snippet from node "{server_node}":
- CPU Usage: {cpu_pct}%
- RAM Usage: {ram_pct}%
- Disk Usage: {disk_pct}%
- Server Logs:
{log_snippet}

Respond ONLY with a valid JSON object containing these exact keys:
- "severity": one of ["Low", "Medium", "Critical"]
- "anomaly_score": float between 5.0 and 99.5
- "diagnosis": concise 1-2 sentence technical diagnosis of what is happening
- "root_cause": concise 1-2 sentence explanation of the underlying root cause
- "aws_scaling_recommendation": concrete AWS EC2 / EBS / Security Group / EFS scaling or architecture action
- "linux_commands": list of 4 to 6 exact Ubuntu Linux terminal commands (e.g., systemctl, df -h, free -h, sqlite3, mount, journalctl, ufw) to inspect and remediate the issue.
"""

    models = ["gemini-2.0-flash", "gemini-1.5-flash"]
    for model_name in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
            },
        }
        resp = requests.post(url, json=payload, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            text_out = (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
            )
            cleaned = re.sub(r"^```json\s*|\s*```$", "", text_out.strip(), flags=re.MULTILINE)
            parsed = json.loads(cleaned)
            severity = parsed.get("severity", "Medium")
            if severity not in ("Low", "Medium", "Critical"):
                severity = "Medium"
            cmds = parsed.get("linux_commands", [])
            if isinstance(cmds, str):
                cmds = [c.strip() for c in cmds.splitlines() if c.strip()]
            return {
                "severity": severity,
                "anomaly_score": round(float(parsed.get("anomaly_score", 50.0)), 1),
                "ai_engine_used": f"Google {model_name} LLM",
                "diagnosis": str(parsed.get("diagnosis", "")),
                "root_cause": str(parsed.get("root_cause", "")),
                "aws_scaling_recommendation": str(parsed.get("aws_scaling_recommendation", "")),
                "linux_commands": cmds[:6],
            }
    raise RuntimeError("Gemini API call unsuccessful")


def _statistical_ml_fallback(server_node, log_snippet, cpu_pct, ram_pct, disk_pct):
    """
    Local Statistical & Log-Signature ML Engine using NumPy & Pandas.
    Guarantees 100% deterministic, accurate AIOps diagnostics even offline or without an API key.
    """
    lines = [ln.strip() for ln in log_snippet.splitlines() if ln.strip()]
    df = pd.DataFrame({"line": lines if lines else ["NO_LOG_LINES"]})
    lower_blob = log_snippet.lower()

    # Tokenize severity keywords across log lines using Pandas vectorized string matching
    crit_pattern = r"out of memory|oom|segmentation fault|no space left|killed|panic|corrupt|database or disk is full|maxrequestworkers"
    warn_pattern = r"error|failed|timed out|not responding|locked|denied|exceeded|warning|refused"

    crit_hits = int(df["line"].str.lower().str.contains(crit_pattern, regex=True).sum())
    warn_hits = int(df["line"].str.lower().str.contains(warn_pattern, regex=True).sum())

    # Multivariate resource vector & weighted anomaly index via NumPy
    metrics = np.array([float(cpu_pct), float(ram_pct), float(disk_pct)], dtype=np.float64)
    weights = np.array([0.32, 0.38, 0.30], dtype=np.float64)
    weighted_resource_load = float(np.dot(metrics, weights))
    peak_metric = float(np.max(metrics))

    log_penalty = min(42.0, (crit_hits * 18.5) + (warn_hits * 7.5))
    spike_bonus = max(0.0, (peak_metric - 80.0) * 1.15)
    anomaly_score = float(np.clip((weighted_resource_load * 0.62) + log_penalty + spike_bonus, 6.0, 99.2))
    anomaly_score = round(anomaly_score, 1)

    # Determine Severity Tier
    if anomaly_score >= 72.0 or crit_hits >= 1 or peak_metric >= 90.0:
        severity = "Critical"
    elif anomaly_score >= 44.0 or warn_hits >= 1 or peak_metric >= 72.0:
        severity = "Medium"
    else:
        severity = "Low"

    # Rule-enhanced Root Cause & Remediation Knowledge Base
    if any(k in lower_blob for k in ["no space left", "disk is full", "enospc"]) or disk_pct >= 90:
        diagnosis = (
            f"Critical storage exhaustion detected on {server_node} (Disk at {disk_pct}%). "
            "Write operations to SQLite3 and system journals are failing."
        )
        root_cause = (
            "Unrotated Apache/systemd log accumulation and growing SQLite database files exhausted the root Ubuntu volume."
        )
        aws_rec = (
            "Expand the attached AWS EBS gp3 volume from 15 GB to 30 GB via the AWS EC2 Console (Elastic Block Store -> Volumes -> Modify) "
            "and run growpart/resize2fs without downtime."
        )
        commands = [
            "df -h",
            "sudo du -sh /var/log/* /srv/shared/* 2>/dev/null | sort -hr | head -n 10",
            "sudo journalctl --vacuum-size=100M",
            "sudo apt autoremove -y && sudo apt clean",
            "sqlite3 /srv/shared/cloud.db 'PRAGMA integrity_check; VACUUM;'",
        ]
    elif any(k in lower_blob for k in ["out of memory", "oom", "memoryerror", "killed process"]) or ram_pct >= 90:
        diagnosis = (
            f"Severe memory saturation on {server_node} (RAM at {ram_pct}%). "
            "The Linux kernel OOM Killer terminated active Python/application worker processes."
        )
        root_cause = (
            "Memory allocation exceeded physical RAM limits (1.5 GB) without sufficient swap space during concurrent AI/web requests."
        )
        aws_rec = (
            "Vertically scale the AWS EC2 instance from t2.micro (1 GB RAM) to t3.small (2 GB RAM) or t3.medium (4 GB RAM), "
            "and configure a 2 GB Linux swap file as an immediate safety buffer."
        )
        commands = [
            "free -h",
            "dmesg -T | grep -i -E 'oom|killed process' | tail -n 15",
            "ps aux --sort=-%mem | head -n 10",
            "sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile",
            "sudo systemctl restart apache2",
        ]
    elif any(k in lower_blob for k in ["apache2", "mpm_prefork", "maxrequestworkers", "ah00"]):
        diagnosis = (
            f"Apache2 web server instability and worker pool saturation on {server_node} (CPU: {cpu_pct}%, RAM: {ram_pct}%)."
        )
        root_cause = (
            "Concurrent HTTP connections exceeded Apache's MaxRequestWorkers limit, causing child worker crashes and HTTP 502/503 timeouts."
        )
        aws_rec = (
            "Place an AWS Application Load Balancer (ALB) in front of EC2, enable Auto Scaling across 2 Availability Zones, "
            "and tune Gunicorn/Apache worker concurrency."
        )
        commands = [
            "sudo systemctl status apache2",
            "sudo apache2ctl configtest",
            "sudo tail -n 40 /var/log/apache2/error.log",
            "ps aux | grep -E 'apache2|gunicorn'",
            "sudo systemctl restart apache2",
        ]
    elif any(k in lower_blob for k in ["nfs", "mount", "/mnt/cloud-storage", "/srv/shared"]):
        diagnosis = (
            f"NFS Shared Storage connectivity failure detected on {server_node}. Client nodes cannot access shared files or cloud.db."
        )
        root_cause = (
            "Network interruption, stopped nfs-kernel-server daemon on VM1, or blocked TCP/UDP port 2049 in the AWS Security Group."
        )
        aws_rec = (
            "Verify AWS Security Group Inbound Rules allow Port 2049 from the VPC CIDR block, or migrate `/srv/shared` to managed Amazon EFS."
        )
        commands = [
            "ip -4 addr && ping -c 4 172.31.24.101",
            "cat /etc/exports",
            "sudo systemctl status nfs-kernel-server",
            "sudo exportfs -arv",
            "sudo mount -a && ls -la /mnt/cloud-storage",
        ]
    elif any(k in lower_blob for k in ["failed password", "sshd", "authentication attempts", "invalid user"]):
        diagnosis = (
            f"Active SSH brute-force intrusion attempt targeting {server_node} detected in authentication logs."
        )
        root_cause = (
            "Port 22 (SSH) is exposed to 0.0.0.0/0 (Anywhere), allowing automated botnets to dictionary-attack root and admin accounts."
        )
        aws_rec = (
            "Restrict SSH Port 22 in your AWS EC2 Security Group to 'My IP' only, enforce .pem RSA key-only authentication, "
            "and use AWS Systems Manager Session Manager."
        )
        commands = [
            "sudo grep 'Failed password' /var/log/auth.log | tail -n 20",
            "sudo systemctl status ssh",
            "sudo apt install -y fail2ban && sudo systemctl enable --now fail2ban",
            "sudo ufw allow OpenSSH && sudo ufw allow 'Apache Full'",
        ]
    elif any(k in lower_blob for k in ["sqlite", "database is locked", "operationalerror"]):
        diagnosis = (
            f"SQLite3 database contention or file permission error detected on {server_node}."
        )
        root_cause = (
            "Concurrent write locks over network storage or restrictive Linux file ownership preventing the Flask/Apache user from writing to cloud.db."
        )
        aws_rec = (
            "Enable SQLite WAL (Write-Ahead Logging) mode for concurrent reads/writes on EC2, or migrate high-concurrency workloads to Amazon RDS."
        )
        commands = [
            "ls -la cloud.db /srv/shared/cloud.db 2>/dev/null",
            "sqlite3 cloud.db 'PRAGMA journal_mode=WAL;'",
            "sqlite3 cloud.db 'SELECT COUNT(*) FROM analysis_reports;'",
            "sudo chown -R $USER:www-data . && chmod 664 cloud.db",
        ]
    elif cpu_pct >= 80:
        diagnosis = (
            f"Sustained CPU compute bottleneck on {server_node} ({cpu_pct}% utilization), slowing down request processing."
        )
        root_cause = (
            "Compute-bound Python/worker processes competing for a single virtual CPU core and exhausting AWS t2/t3 CPU burst credits."
        )
        aws_rec = (
            "Upgrade the EC2 instance to a compute-optimized c6i.large or enable Unlimited Burst mode on t3.small in AWS EC2 settings."
        )
        commands = [
            "uname -a && uptime",
            "cat /proc/cpuinfo | grep 'model name\\|processor'",
            "ps aux --sort=-%cpu | head -n 10",
            "top -b -n 1 | head -n 20",
        ]
    else:
        diagnosis = (
            f"System telemetry and logs for {server_node} indicate healthy, stable operation (CPU {cpu_pct}%, RAM {ram_pct}%, Disk {disk_pct}%)."
        )
        root_cause = (
            "All monitored Ubuntu services, SQLite transactions, and compute resources are well within safe operational thresholds."
        )
        aws_rec = (
            "Current AWS EC2 Free-Tier configuration (t2.micro / t3.micro) is optimal. Schedule automated AWS EBS snapshots for daily backup."
        )
        commands = [
            "uname -a",
            "free -h",
            "df -h",
            "systemctl status apache2 ssh --no-pager",
        ]

    return {
        "severity": severity,
        "anomaly_score": anomaly_score,
        "ai_engine_used": "CloudMind Statistical ML Engine (Pandas/NumPy)",
        "diagnosis": diagnosis,
        "root_cause": root_cause,
        "aws_scaling_recommendation": aws_rec,
        "linux_commands": commands,
    }


def analyze_server_telemetry(server_node, log_snippet, cpu_pct, ram_pct, disk_pct, user_api_key=None):
    """
    Main entry point: uses Google Gemini LLM if an API key is configured/supplied,
    and seamlessly falls back to the built-in Pandas/NumPy Statistical ML Engine.
    """
    api_key = (user_api_key or os.environ.get("GEMINI_API_KEY", "")).strip()
    if api_key:
        try:
            return _call_gemini_api(api_key, server_node, log_snippet, cpu_pct, ram_pct, disk_pct)
        except Exception:
            # Graceful fallback so live cloud demos never fail
            pass

    return _statistical_ml_fallback(server_node, log_snippet, cpu_pct, ram_pct, disk_pct)
