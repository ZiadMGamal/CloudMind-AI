import json
import os
import sqlite3
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("CLOUDMIND_DB_PATH", os.path.join(BASE_DIR, "cloud.db"))


def get_db_connection():
    """Create a connection to the SQLite3 database with Row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize SQLite3 tables (nodes & analysis_reports) and seed initial cluster data."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Table 1: Cloud Cluster Virtual Machine Nodes (Aligned with Lab Task 1)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS nodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hostname TEXT NOT NULL UNIQUE,
            vm_label TEXT NOT NULL,
            role TEXT NOT NULL,
            ip_address TEXT NOT NULL,
            instance_type TEXT NOT NULL,
            cpu_usage REAL DEFAULT 25.0,
            ram_usage_mb INTEGER DEFAULT 512,
            ram_total_mb INTEGER DEFAULT 1536,
            disk_usage_gb REAL DEFAULT 4.5,
            disk_total_gb REAL DEFAULT 15.0,
            status TEXT DEFAULT 'Running',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    # Table 2: AI Log & Resource Analysis Reports
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS analysis_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            server_node TEXT NOT NULL,
            log_snippet TEXT NOT NULL,
            cpu_pct REAL NOT NULL,
            ram_pct REAL NOT NULL,
            disk_pct REAL NOT NULL,
            severity TEXT NOT NULL,
            anomaly_score REAL NOT NULL,
            ai_engine_used TEXT NOT NULL,
            diagnosis TEXT NOT NULL,
            root_cause TEXT NOT NULL,
            aws_scaling_recommendation TEXT NOT NULL,
            linux_commands TEXT NOT NULL,
            resolution_status TEXT DEFAULT 'Open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    # Seed the 3 Cloud VMs if empty
    cursor.execute("SELECT COUNT(*) AS count FROM nodes;")
    if cursor.fetchone()["count"] == 0:
        seed_nodes = [
            (
                "server",
                "VM1 — Server",
                "Apache2 Web Server + SQLite3 DB + NFS Shared Storage (/srv/shared)",
                "172.31.24.101",
                "AWS t2.micro (1 vCPU, 1.5 GB)",
                42.5,
                890,
                1536,
                7.8,
                15.0,
                "Running",
            ),
            (
                "client",
                "VM2 — Client",
                "Client Web Applications + NFS Mount (/mnt/cloud-storage)",
                "172.31.24.102",
                "AWS t2.micro (1 vCPU, 1.5 GB)",
                28.0,
                540,
                1536,
                4.2,
                15.0,
                "Running",
            ),
            (
                "worker",
                "VM3 — Worker",
                "AI Log Anomaly Detection & Batch Processing Node",
                "172.31.24.103",
                "AWS t3.small (2 vCPU, 2.0 GB)",
                68.4,
                1420,
                2048,
                9.6,
                15.0,
                "Warning",
            ),
        ]
        cursor.executemany(
            """
            INSERT INTO nodes (
                hostname, vm_label, role, ip_address, instance_type,
                cpu_usage, ram_usage_mb, ram_total_mb, disk_usage_gb, disk_total_gb, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            seed_nodes,
        )

    # Seed initial AI reports so Dashboard & History have rich sample data out of the box
    cursor.execute("SELECT COUNT(*) AS count FROM analysis_reports;")
    if cursor.fetchone()["count"] == 0:
        now = datetime.utcnow()
        seed_reports = [
            (
                "VM1 — Server (server)",
                "[Sun Oct 30 14:12:09.412 2026] [mpm_prefork:error] [pid 1842] AH00161: server reached MaxRequestWorkers setting, consider raising the MaxRequestWorkers setting\n[Sun Oct 30 14:12:11.104 2026] [core:error] AH00052: child pid 2019 exit signal Segmentation fault (11)",
                89.0,
                91.5,
                62.0,
                "Critical",
                91.4,
                "CloudMind Statistical ML Engine",
                "Apache2 Web Server worker pool exhaustion accompanied by high CPU (89%) and memory saturation (91.5%). Incoming HTTP requests are queueing and dropping.",
                "Traffic spike exceeded Apache mpm_prefork MaxRequestWorkers on a 1-vCPU instance, causing worker process starvation and memory pressure.",
                "Upgrade VM1 EC2 instance from t2.micro to t3.small (2 vCPUs, 2 GB RAM) and place an AWS Application Load Balancer in front of Apache2.",
                json.dumps(
                    [
                        "sudo systemctl status apache2",
                        "sudo tail -n 50 /var/log/apache2/error.log",
                        "free -h && ps aux --sort=-%mem | head -n 10",
                        "sudo systemctl restart apache2",
                    ]
                ),
                "Open",
                (now - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S"),
            ),
            (
                "VM2 — Client (client)",
                "mount.nfs: Connection timed out for 172.31.24.101:/srv/shared on /mnt/cloud-storage\nsqlite3.OperationalError: unable to open database file: /mnt/cloud-storage/cloud.db",
                34.0,
                48.0,
                55.0,
                "Medium",
                64.2,
                "CloudMind Statistical ML Engine",
                "NFS Shared Storage mount disconnection between VM2 (Client) and VM1 (Server), preventing SQLite3 shared database access.",
                "NFS kernel server daemon on VM1 stopped responding or AWS Security Group blocked port 2049 between subnet nodes.",
                "Allow TCP/UDP Port 2049 within the AWS VPC Security Group or migrate shared storage to Amazon EFS (Elastic File System) for managed high availability.",
                json.dumps(
                    [
                        "ping -c 4 172.31.24.101",
                        "cat /etc/exports",
                        "sudo systemctl restart nfs-kernel-server",
                        "sudo mount -t nfs 172.31.24.101:/srv/shared /mnt/cloud-storage",
                        "ls -l /mnt/cloud-storage",
                    ]
                ),
                "In Progress",
                (now - timedelta(hours=1, minutes=30)).strftime("%Y-%m-%d %H:%M:%S"),
            ),
            (
                "VM3 — Worker (worker)",
                "systemd[1]: Started CloudMind AI Worker Service.\nINFO: Processed 1,240 telemetry batches in 1.82s. CPU load nominal. Disk check passed.",
                31.0,
                44.0,
                38.0,
                "Low",
                16.5,
                "CloudMind Statistical ML Engine",
                "Cluster node operating within healthy baseline parameters. No error signatures or resource bottlenecks detected.",
                "Normal AI batch processing workload with balanced memory allocation and healthy disk I/O.",
                "Maintain current AWS EC2 instance sizing. Enable AWS CloudWatch basic metrics alarm at >80% CPU utilization.",
                json.dumps(
                    [
                        "uname -a",
                        "free -h",
                        "df -h",
                    ]
                ),
                "Resolved",
                (now - timedelta(minutes=25)).strftime("%Y-%m-%d %H:%M:%S"),
            ),
        ]
        cursor.executemany(
            """
            INSERT INTO analysis_reports (
                server_node, log_snippet, cpu_pct, ram_pct, disk_pct,
                severity, anomaly_score, ai_engine_used, diagnosis, root_cause,
                aws_scaling_recommendation, linux_commands, resolution_status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            seed_reports,
        )

    conn.commit()
    conn.close()


def get_all_nodes():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM nodes ORDER BY id ASC;").fetchall()
    conn.close()
    nodes = []
    for r in rows:
        item = dict(r)
        item["ram_pct"] = round((item["ram_usage_mb"] / max(item["ram_total_mb"], 1)) * 100, 1)
        item["disk_pct"] = round((item["disk_usage_gb"] / max(item["disk_total_gb"], 0.1)) * 100, 1)
        nodes.append(item)
    return nodes


def update_node_metrics(node_id, cpu_usage, ram_usage_mb, disk_usage_gb):
    cpu_val = max(1.0, min(100.0, float(cpu_usage)))
    ram_val = max(64, int(float(ram_usage_mb)))
    disk_val = max(0.5, float(disk_usage_gb))

    conn = get_db_connection()
    node = conn.execute("SELECT * FROM nodes WHERE id = ?;", (node_id,)).fetchone()
    if not node:
        conn.close()
        return False

    ram_pct = (ram_val / max(node["ram_total_mb"], 1)) * 100.0
    disk_pct = (disk_val / max(node["disk_total_gb"], 0.1)) * 100.0

    if cpu_val >= 85 or ram_pct >= 88 or disk_pct >= 90:
        status = "Critical"
    elif cpu_val >= 65 or ram_pct >= 70 or disk_pct >= 75:
        status = "Warning"
    else:
        status = "Running"

    conn.execute(
        """
        UPDATE nodes
        SET cpu_usage = ?, ram_usage_mb = ?, disk_usage_gb = ?, status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?;
        """,
        (round(cpu_val, 1), ram_val, round(disk_val, 2), status, node_id),
    )
    conn.commit()
    conn.close()
    return True


def insert_report(report_data):
    conn = get_db_connection()
    cursor = conn.cursor()
    commands_json = json.dumps(report_data.get("linux_commands", []))
    cursor.execute(
        """
        INSERT INTO analysis_reports (
            server_node, log_snippet, cpu_pct, ram_pct, disk_pct,
            severity, anomaly_score, ai_engine_used, diagnosis, root_cause,
            aws_scaling_recommendation, linux_commands, resolution_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            report_data["server_node"],
            report_data["log_snippet"],
            report_data["cpu_pct"],
            report_data["ram_pct"],
            report_data["disk_pct"],
            report_data["severity"],
            report_data["anomaly_score"],
            report_data["ai_engine_used"],
            report_data["diagnosis"],
            report_data["root_cause"],
            report_data["aws_scaling_recommendation"],
            commands_json,
            report_data.get("resolution_status", "Open"),
        ),
    )
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return new_id


def _deserialize_report(row):
    item = dict(row)
    try:
        item["linux_commands_list"] = json.loads(item["linux_commands"])
    except Exception:
        item["linux_commands_list"] = [
            line.strip() for line in item["linux_commands"].splitlines() if line.strip()
        ]
    return item


def get_all_reports(severity_filter=None, search_query=None):
    conn = get_db_connection()
    query = "SELECT * FROM analysis_reports WHERE 1=1"
    params = []

    if severity_filter and severity_filter in ("Low", "Medium", "Critical"):
        query += " AND severity = ?"
        params.append(severity_filter)

    if search_query:
        query += " AND (server_node LIKE ? OR diagnosis LIKE ? OR log_snippet LIKE ? OR root_cause LIKE ?)"
        like_q = f"%{search_query.strip()}%"
        params.extend([like_q, like_q, like_q, like_q])

    query += " ORDER BY id DESC;"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [_deserialize_report(r) for r in rows]


def get_report_by_id(report_id):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM analysis_reports WHERE id = ?;", (report_id,)).fetchone()
    conn.close()
    return _deserialize_report(row) if row else None


def update_report_status(report_id, new_status):
    if new_status not in ("Open", "In Progress", "Resolved"):
        return False
    conn = get_db_connection()
    conn.execute(
        "UPDATE analysis_reports SET resolution_status = ? WHERE id = ?;",
        (new_status, report_id),
    )
    conn.commit()
    conn.close()
    return True


def delete_report(report_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM analysis_reports WHERE id = ?;", (report_id,))
    conn.commit()
    conn.close()
    return True


def get_dashboard_stats():
    conn = get_db_connection()
    total_reports = conn.execute("SELECT COUNT(*) AS c FROM analysis_reports;").fetchone()["c"]
    critical_open = conn.execute(
        "SELECT COUNT(*) AS c FROM analysis_reports WHERE severity = 'Critical' AND resolution_status != 'Resolved';"
    ).fetchone()["c"]
    avg_score_row = conn.execute("SELECT AVG(anomaly_score) AS avg_s FROM analysis_reports;").fetchone()
    avg_score = round(avg_score_row["avg_s"], 1) if avg_score_row["avg_s"] is not None else 0.0

    sev_counts = {"Critical": 0, "Medium": 0, "Low": 0}
    for row in conn.execute(
        "SELECT severity, COUNT(*) AS cnt FROM analysis_reports GROUP BY severity;"
    ).fetchall():
        if row["severity"] in sev_counts:
            sev_counts[row["severity"]] = row["cnt"]

    recent_rows = conn.execute(
        "SELECT id, server_node, severity, anomaly_score, created_at FROM analysis_reports ORDER BY id DESC LIMIT 8;"
    ).fetchall()
    conn.close()

    db_size_kb = round(os.path.getsize(DB_PATH) / 1024.0, 2) if os.path.exists(DB_PATH) else 0.0

    return {
        "total_reports": total_reports,
        "critical_open": critical_open,
        "avg_anomaly_score": avg_score,
        "severity_counts": sev_counts,
        "recent_trend": [dict(r) for r in reversed(recent_rows)],
        "db_size_kb": db_size_kb,
        "db_path": DB_PATH,
    }
