#!/usr/bin/env python3
"""
Audit Log Analyzer for ActiveMirrorOS

Analyzes audit logs to detect security events, generate reports, and identify anomalies.

Usage:
    # Analyze log file
    python tools/analyze_audit_logs.py analyze logs/app.log

    # Generate security report
    python tools/analyze_audit_logs.py report logs/app.log --format html

    # Monitor for anomalies
    python tools/analyze_audit_logs.py monitor logs/app.log --alert-on failures

Author: AMOS Dev Twin
"""

import sys
import argparse
import json
import re
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from typing import List, Dict, Any


class AuditLogAnalyzer:
    """Analyzes ActiveMirrorOS audit logs."""

    def __init__(self, log_file: str):
        self.log_file = Path(log_file)
        self.audit_events = []
        self.security_events = []
        self.errors = []
        self.performance_metrics = []

    def parse_logs(self) -> dict:
        """Parse log file and extract events."""
        if not self.log_file.exists():
            return {"error": f"Log file not found: {self.log_file}"}

        with open(self.log_file, 'r') as f:
            for line_num, line in enumerate(f, 1):
                try:
                    # Try to parse as JSON
                    if line.strip().startswith('{'):
                        log_entry = json.loads(line.strip())
                        self._categorize_entry(log_entry)
                    else:
                        # Try to parse structured text format
                        self._parse_text_format(line)
                except json.JSONDecodeError:
                    # Skip non-JSON lines or parse as text
                    self._parse_text_format(line)
                except Exception as e:
                    # print(f"Warning: Failed to parse line {line_num}: {e}")
                    pass

        return {
            "audit_events": len(self.audit_events),
            "security_events": len(self.security_events),
            "errors": len(self.errors),
            "performance_metrics": len(self.performance_metrics),
        }

    def _categorize_entry(self, entry: dict):
        """Categorize log entry by type."""
        message = entry.get("message", "")
        level = entry.get("level", "INFO")

        if "AUDIT:" in message:
            self.audit_events.append(entry)
        elif "SECURITY:" in message:
            self.security_events.append(entry)
        elif "PERF:" in message:
            self.performance_metrics.append(entry)
        elif level in ("ERROR", "CRITICAL"):
            self.errors.append(entry)

    def _parse_text_format(self, line: str):
        """Parse text-format logs."""
        if "AUDIT:" in line:
            # Extract timestamp and message
            match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*AUDIT: (.+)', line)
            if match:
                timestamp, message = match.groups()
                self.audit_events.append({
                    "timestamp": timestamp,
                    "message": f"AUDIT: {message}",
                    "level": "INFO",
                })
        elif "SECURITY:" in line:
            match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*SECURITY: (.+)', line)
            if match:
                timestamp, message = match.groups()
                self.security_events.append({
                    "timestamp": timestamp,
                    "message": f"SECURITY: {message}",
                    "level": "INFO",
                })
        elif "ERROR" in line or "CRITICAL" in line:
            self.errors.append({
                "message": line.strip(),
                "level": "ERROR" if "ERROR" in line else "CRITICAL",
            })

    def analyze_security_events(self) -> dict:
        """Analyze security events for threats."""
        threats = {
            "failed_vault_access": [],
            "sql_injection_attempts": [],
            "unusual_patterns": [],
        }

        for event in self.audit_events:
            context = event.get("context", {})
            if isinstance(context, str):
                try:
                    context = json.loads(context)
                except:
                    continue

            # Check for failed vault access
            if context.get("action") in ("vault_retrieve", "vault_store", "vault_delete"):
                if context.get("status") == "failure":
                    threats["failed_vault_access"].append({
                        "timestamp": event.get("timestamp"),
                        "action": context.get("action"),
                        "resource": context.get("resource"),
                        "error": context.get("details", {}).get("error"),
                    })

        return threats

    def generate_summary(self) -> dict:
        """Generate summary statistics."""
        # Count operations by type
        operation_counts = Counter()
        failed_operations = Counter()
        operations_by_hour = defaultdict(int)

        for event in self.audit_events:
            context = event.get("context", {})
            if isinstance(context, str):
                try:
                    context = json.loads(context)
                except:
                    continue

            action = context.get("action", "unknown")
            status = context.get("status", "unknown")

            operation_counts[action] += 1

            if status == "failure":
                failed_operations[action] += 1

            # Parse timestamp for hourly breakdown
            timestamp = event.get("timestamp")
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    hour_key = dt.strftime("%Y-%m-%d %H:00")
                    operations_by_hour[hour_key] += 1
                except:
                    pass

        return {
            "total_operations": sum(operation_counts.values()),
            "operations_by_type": dict(operation_counts.most_common()),
            "failed_operations": dict(failed_operations),
            "operations_by_hour": dict(sorted(operations_by_hour.items())),
            "error_count": len(self.errors),
            "security_event_count": len(self.security_events),
        }

    def detect_anomalies(self) -> List[dict]:
        """Detect anomalous patterns."""
        anomalies = []

        # Check for excessive failures
        summary = self.generate_summary()
        failed_ops = summary["failed_operations"]

        for operation, count in failed_ops.items():
            total = summary["operations_by_type"].get(operation, 0)
            if total > 0:
                failure_rate = count / total
                if failure_rate > 0.3:  # >30% failure rate
                    anomalies.append({
                        "type": "high_failure_rate",
                        "operation": operation,
                        "failure_rate": f"{failure_rate:.1%}",
                        "failures": count,
                        "total": total,
                        "severity": "high" if failure_rate > 0.5 else "medium",
                    })

        # Check for unusual access patterns
        vault_accesses = defaultdict(int)
        for event in self.audit_events:
            context = event.get("context", {})
            if isinstance(context, str):
                try:
                    context = json.loads(context)
                except:
                    continue

            if "vault_" in context.get("action", ""):
                resource = context.get("resource", "unknown")
                vault_accesses[resource] += 1

        # Flag resources accessed unusually often
        if vault_accesses:
            avg_accesses = sum(vault_accesses.values()) / len(vault_accesses)
            for resource, count in vault_accesses.items():
                if count > avg_accesses * 5:  # 5x more than average
                    anomalies.append({
                        "type": "unusual_access_pattern",
                        "resource": resource,
                        "access_count": count,
                        "average": f"{avg_accesses:.1f}",
                        "severity": "low",
                    })

        return anomalies

    def generate_report(self, format: str = "text") -> str:
        """Generate security report."""
        summary = self.generate_summary()
        threats = self.analyze_security_events()
        anomalies = self.detect_anomalies()

        if format == "json":
            return json.dumps({
                "summary": summary,
                "threats": threats,
                "anomalies": anomalies,
            }, indent=2)

        elif format == "html":
            return self._generate_html_report(summary, threats, anomalies)

        else:  # text
            report = []
            report.append("=" * 70)
            report.append("ACTIVEMIRROR AUDIT LOG ANALYSIS REPORT")
            report.append("=" * 70)
            report.append("")

            # Summary
            report.append("SUMMARY")
            report.append("-" * 70)
            report.append(f"Total Operations:    {summary['total_operations']}")
            report.append(f"Security Events:     {summary['security_event_count']}")
            report.append(f"Errors:              {summary['error_count']}")
            report.append("")

            # Operations breakdown
            report.append("OPERATIONS BY TYPE")
            report.append("-" * 70)
            for op, count in summary["operations_by_type"].items():
                failures = summary["failed_operations"].get(op, 0)
                failure_indicator = f" ({failures} failed)" if failures > 0 else ""
                report.append(f"  {op:30s} {count:5d}{failure_indicator}")
            report.append("")

            # Threats
            if any(threats.values()):
                report.append("SECURITY THREATS DETECTED")
                report.append("-" * 70)

                if threats["failed_vault_access"]:
                    report.append(f"❌ Failed Vault Access: {len(threats['failed_vault_access'])} attempts")
                    for attempt in threats["failed_vault_access"][:5]:  # Show first 5
                        report.append(f"   - {attempt['timestamp']}: {attempt['action']} on {attempt['resource']}")
                    if len(threats["failed_vault_access"]) > 5:
                        report.append(f"   ... and {len(threats['failed_vault_access']) - 5} more")
                report.append("")

            # Anomalies
            if anomalies:
                report.append("ANOMALIES DETECTED")
                report.append("-" * 70)
                for anomaly in anomalies:
                    severity_icon = "🔴" if anomaly["severity"] == "high" else "🟡" if anomaly["severity"] == "medium" else "🟢"
                    report.append(f"{severity_icon} {anomaly['type']}")
                    for key, value in anomaly.items():
                        if key not in ("type", "severity"):
                            report.append(f"     {key}: {value}")
                report.append("")

            report.append("=" * 70)

            return "\n".join(report)

    def _generate_html_report(self, summary: dict, threats: dict, anomalies: list) -> str:
        """Generate HTML report."""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>ActiveMirror Audit Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; }}
        h1 {{ color: #333; border-bottom: 3px solid #4CAF50; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; }}
        .metric {{ display: inline-block; margin: 15px; padding: 20px; background: #e8f5e9; border-radius: 5px; }}
        .metric-value {{ font-size: 36px; font-weight: bold; color: #2e7d32; }}
        .metric-label {{ color: #666; font-size: 14px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #4CAF50; color: white; }}
        .threat {{ background: #ffebee; padding: 15px; margin: 10px 0; border-left: 4px solid #f44336; }}
        .anomaly {{ background: #fff3e0; padding: 15px; margin: 10px 0; border-left: 4px solid #ff9800; }}
        .severity-high {{ color: #d32f2f; }}
        .severity-medium {{ color: #f57c00; }}
        .severity-low {{ color: #388e3c; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>ActiveMirror Audit Log Analysis</h1>
        <p>Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>

        <h2>Summary</h2>
        <div class="metric">
            <div class="metric-value">{summary['total_operations']}</div>
            <div class="metric-label">Total Operations</div>
        </div>
        <div class="metric">
            <div class="metric-value">{summary['security_event_count']}</div>
            <div class="metric-label">Security Events</div>
        </div>
        <div class="metric">
            <div class="metric-value">{summary['error_count']}</div>
            <div class="metric-label">Errors</div>
        </div>

        <h2>Operations by Type</h2>
        <table>
            <tr><th>Operation</th><th>Count</th><th>Failures</th></tr>
"""

        for op, count in summary["operations_by_type"].items():
            failures = summary["failed_operations"].get(op, 0)
            html += f"<tr><td>{op}</td><td>{count}</td><td>{failures}</td></tr>\n"

        html += "</table>"

        # Threats
        if threats["failed_vault_access"]:
            html += "<h2>Security Threats</h2>"
            for attempt in threats["failed_vault_access"][:10]:
                html += f"""
                <div class="threat">
                    <strong>Failed Vault Access</strong><br>
                    Time: {attempt['timestamp']}<br>
                    Action: {attempt['action']}<br>
                    Resource: {attempt['resource']}
                </div>
                """

        # Anomalies
        if anomalies:
            html += "<h2>Anomalies Detected</h2>"
            for anomaly in anomalies:
                html += f'<div class="anomaly"><span class="severity-{anomaly["severity"]}">{anomaly["type"]}</span><br>'
                for key, value in anomaly.items():
                    if key not in ("type", "severity"):
                        html += f"{key}: {value}<br>"
                html += "</div>"

        html += """
    </div>
</body>
</html>
"""
        return html


def main():
    parser = argparse.ArgumentParser(description="ActiveMirrorOS Audit Log Analyzer")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze audit logs")
    analyze_parser.add_argument("log_file", help="Path to log file")

    # Report command
    report_parser = subparsers.add_parser("report", help="Generate security report")
    report_parser.add_argument("log_file", help="Path to log file")
    report_parser.add_argument("--format", "-f", choices=["text", "json", "html"], default="text")
    report_parser.add_argument("--output", "-o", help="Output file (default: stdout)")

    # Monitor command
    monitor_parser = subparsers.add_parser("monitor", help="Monitor for anomalies")
    monitor_parser.add_argument("log_file", help="Path to log file")
    monitor_parser.add_argument("--alert-on", choices=["failures", "anomalies", "all"], default="all")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    analyzer = AuditLogAnalyzer(args.log_file)
    print(f"📖 Parsing log file: {args.log_file}")
    stats = analyzer.parse_logs()

    if "error" in stats:
        print(f"❌ {stats['error']}")
        sys.exit(1)

    print(f"✅ Parsed {stats['audit_events']} audit events, {stats['security_events']} security events")
    print()

    if args.command == "analyze":
        summary = analyzer.generate_summary()
        print("SUMMARY:")
        print(f"  Total operations: {summary['total_operations']}")
        print(f"  Errors: {summary['error_count']}")
        print(f"  Security events: {summary['security_event_count']}")
        print()

        print("TOP OPERATIONS:")
        for op, count in list(summary["operations_by_type"].items())[:5]:
            print(f"  {op}: {count}")

    elif args.command == "report":
        report = analyzer.generate_report(args.format)

        if args.output:
            with open(args.output, 'w') as f:
                f.write(report)
            print(f"📝 Report saved to: {args.output}")
        else:
            print(report)

    elif args.command == "monitor":
        anomalies = analyzer.detect_anomalies()

        if anomalies:
            print("⚠️  ANOMALIES DETECTED:")
            for anomaly in anomalies:
                severity_icon = "🔴" if anomaly["severity"] == "high" else "🟡" if anomaly["severity"] == "medium" else "🟢"
                print(f"{severity_icon} {anomaly['type']}: {anomaly}")
            sys.exit(1)
        else:
            print("✅ No anomalies detected")


if __name__ == "__main__":
    main()
