import csv
import io
import json
import os
import platform
import socket
import subprocess
from datetime import datetime
from flask import (
    Flask,
    Response,
    flash,
     jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from ai_engine import SAMPLE_SCENARIOS, analyze_server_telemetry
from database import (
    delete_report,
    get_all_nodes,
    get_all_reports,
    get_dashboard_stats,
    get_report_by_id,
    init_db,
    insert_report,
    update_node_metrics,
    update_report_status,
)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "cloudmind-aws-final-project-2026")

# Ensure SQLite3 database (cloud.db) and seed data exist on startup
init_db()


def _run_cmd(cmd_list):
    """Safely execute a read-only Linux system command with timeout."""
    try:
        out = subprocess.check_output(cmd_list, stderr=subprocess.DEVNULL, timeout=2)
        return out.decode("utf-8", errors="replace").strip()
    except Exception:
        return None


def get_host_telemetry():
    """
    Read live OS & hardware metrics directly from the Ubuntu host when deployed on AWS EC2,
    with seamless cross-platform support when previewing locally on Windows/macOS.
    """
    sys_name = platform.system()
    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except Exception:
        local_ip = "127.0.0.1"

    if sys_name == "Linux":
        uname_str = _run_cmd(["uname", "-a"]) or platform.platform()
        free_str = _run_cmd(["free", "-h"]) or "Memory telemetry unavailable"
        df_str = _run_cmd(["df", "-h", "/"]) or "Disk telemetry unavailable"
        uptime_str = _run_cmd(["uptime", "-p"]) or "up (active)"
        environment_badge = "AWS EC2 Ubuntu Linux Host (Live)"
    else:
        uname_str = f"{sys_name} {platform.release()} ({platform.machine()}) — Local Dev Preview (Deploys to Ubuntu 24.04 LTS on AWS EC2)"
        free_str = "Mem:          1.5Gi       890Mi       310Mi        12Mi       336Mi       520Mi"
        df_str = "Filesystem      Size  Used Avail Use% Mounted on\n/dev/root        15G  7.8G  7.2G  52% /"
        uptime_str = "Local Development Mode"
        environment_badge = "Local Preview Mode (AWS Ready)"

    return {
        "hostname": hostname,
        "local_ip": local_ip,
        "os_platform": sys_name,
        "uname": uname_str,
        "free_output": free_str,
        "df_output": df_str,
        "uptime": uptime_str,
        "environment_badge": environment_badge,
        "gemini_configured": bool(os.environ.get("GEMINI_API_KEY", "").strip()),
    }


@app.route("/")
def dashboard():
    """Page 1: AWS Cloud Cluster Dashboard & Live Telemetry Monitor."""
    nodes = get_all_nodes()
    stats = get_dashboard_stats()
    host_info = get_host_telemetry()
    recent_reports = get_all_reports()[:4]
    return render_template(
        "index.html",
        nodes=nodes,
        stats=stats,
        host_info=host_info,
        recent_reports=recent_reports,
        active_page="dashboard",
    )


@app.route("/nodes/update", methods=["POST"])
def update_node():
    """Update VM CPU/RAM/Disk metrics in SQLite3 (demonstrates SQL UPDATE on nodes)."""
    node_id = request.form.get("node_id", type=int)
    cpu_usage = request.form.get("cpu_usage", 35.0, type=float)
    ram_usage_mb = request.form.get("ram_usage_mb", 600, type=int)
    disk_usage_gb = request.form.get("disk_usage_gb", 5.0, type=float)

    if node_id and update_node_metrics(node_id, cpu_usage, ram_usage_mb, disk_usage_gb):
        flash("Cloud VM telemetry updated in SQLite3 (cloud.db) successfully!", "success")
    else:
        flash("Unable to update Cloud VM node metrics.", "error")
    return redirect(url_for("dashboard"))


@app.route("/analyzer", methods=["GET", "POST"])
def analyzer():
    """Page 2: AI Log & Resource Bottleneck Analyzer."""
    nodes = get_all_nodes()
    analysis_result = None
    saved_report_id = None

    form_defaults = {
        "server_node": "VM1 — Server (server)",
        "cpu_pct": 78,
        "ram_pct": 84,
        "disk_pct": 55,
        "log_snippet": "",
    }

    if request.method == "POST":
        server_node = request.form.get("server_node", "VM1 — Server (server)").strip()
        cpu_pct = request.form.get("cpu_pct", 50.0, type=float)
        ram_pct = request.form.get("ram_pct", 50.0, type=float)
        disk_pct = request.form.get("disk_pct", 50.0, type=float)
        log_snippet = request.form.get("log_snippet", "").strip()
        user_api_key = request.form.get("api_key", "").strip()

        # Support optional .log / .txt file upload
        uploaded_file = request.files.get("log_file")
        if uploaded_file and uploaded_file.filename:
            file_content = uploaded_file.read(65536).decode("utf-8", errors="replace").strip()
            if file_content:
                log_snippet = file_content

        if not log_snippet:
            log_snippet = (
                f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}] Automated telemetry check on {server_node} "
                f"(CPU={cpu_pct}%, RAM={ram_pct}%, Disk={disk_pct}%)"
            )

        form_defaults = {
            "server_node": server_node,
            "cpu_pct": int(cpu_pct),
            "ram_pct": int(ram_pct),
            "disk_pct": int(disk_pct),
            "log_snippet": log_snippet,
        }

        ai_out = analyze_server_telemetry(
            server_node=server_node,
            log_snippet=log_snippet,
            cpu_pct=cpu_pct,
            ram_pct=ram_pct,
            disk_pct=disk_pct,
            user_api_key=user_api_key,
        )

        report_payload = {
            "server_node": server_node,
            "log_snippet": log_snippet,
            "cpu_pct": round(cpu_pct, 1),
            "ram_pct": round(ram_pct, 1),
            "disk_pct": round(disk_pct, 1),
            **ai_out,
        }
        saved_report_id = insert_report(report_payload)
        analysis_result = get_report_by_id(saved_report_id)
        flash(
            f"AI analysis completed and saved to SQLite3 (Report #{saved_report_id}).",
            "success",
        )

    return render_template(
        "analyzer.html",
        nodes=nodes,
        scenarios=SAMPLE_SCENARIOS,
        scenarios_json=json.dumps(SAMPLE_SCENARIOS),
        form_data=form_defaults,
        result=analysis_result,
        saved_report_id=saved_report_id,
        active_page="analyzer",
    )


@app.route("/history")
def history():
    """Page 3: SQLite3 Database Explorer & Audit History."""
    severity_filter = request.args.get("severity", "").strip()
    search_query = request.args.get("q", "").strip()
    reports = get_all_reports(severity_filter=severity_filter, search_query=search_query)
    stats = get_dashboard_stats()
    return render_template(
        "history.html",
        reports=reports,
        stats=stats,
        severity_filter=severity_filter,
        search_query=search_query,
        active_page="history",
    )


@app.route("/history/update/<int:report_id>", methods=["POST"])
def history_update_status(report_id):
    """Execute SQL UPDATE on analysis_reports resolution_status."""
    new_status = request.form.get("resolution_status", "Open")
    if update_report_status(report_id, new_status):
        flash(f"Report #{report_id} status updated to '{new_status}' in SQLite3.", "success")
    else:
        flash("Invalid status value.", "error")
    return redirect(url_for("history"))


@app.route("/history/delete/<int:report_id>", methods=["POST"])
def history_delete(report_id):
    """Execute SQL DELETE FROM analysis_reports WHERE id = ?."""
    delete_report(report_id)
    flash(f"Report #{report_id} deleted from SQLite3 (cloud.db).", "success")
    return redirect(url_for("history"))


@app.route("/export/json")
def export_json():
    """Export all SQLite3 AI analysis reports as downloadable JSON."""
    reports = get_all_reports()
    payload = json.dumps(reports, indent=2)
    return Response(
        payload,
        mimetype="application/json",
        headers={"Content-Disposition": "attachment;filename=cloudmind_ai_reports.json"},
    )


@app.route("/export/csv")
def export_csv():
    """Export all SQLite3 AI analysis reports as downloadable CSV."""
    reports = get_all_reports()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "ID",
            "Server Node",
            "Severity",
            "Anomaly Score",
            "CPU %",
            "RAM %",
            "Disk %",
            "AI Engine",
            "Diagnosis",
            "Root Cause",
            "AWS Scaling Recommendation",
            "Resolution Status",
            "Created At",
        ]
    )
    for r in reports:
        writer.writerow(
            [
                r["id"],
                r["server_node"],
                r["severity"],
                r["anomaly_score"],
                r["cpu_pct"],
                r["ram_pct"],
                r["disk_pct"],
                r["ai_engine_used"],
                r["diagnosis"],
                r["root_cause"],
                r["aws_scaling_recommendation"],
                r["resolution_status"],
                r["created_at"],
            ]
        )
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=cloudmind_ai_reports.csv"},
    )


@app.route("/api/health")
def api_health():
    """Cloud Provider Health-Check Endpoint (for AWS ALB / uptime monitoring)."""
    stats = get_dashboard_stats()
    return jsonify(
        {
            "status": "healthy",
            "service": "CloudMind AI — Smart Cloud Resource & Log Analyzer",
            "database": "SQLite3 (cloud.db) connected",
            "total_reports": stats["total_reports"],
            "timestamp_utc": datetime.utcnow().isoformat() + "Z",
        }
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
