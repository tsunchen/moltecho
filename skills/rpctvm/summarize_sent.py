#!/usr/bin/env python3
"""
Email Sent Folder Summary Tool

Reads emails from the Sent folder and generates summary reports.
Configured for 163.com mailbox (requires IMAP ID command).

Usage:
    python summarize_sent.py --days 1
    python summarize_sent.py --days 7  # Weekly report
"""

import imaplib
import email
from email.header import decode_header
import json
import os
import re
import argparse
from datetime import datetime, timedelta, timezone


def get_email_content(msg):
    """Extract plain text content from email message."""
    content = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            if content_type == "text/plain" and "attachment" not in content_disposition:
                try:
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset()
                    content += payload.decode(charset if charset else 'utf-8', errors='replace')
                except:
                    pass
            elif content_type == "text/html" and "attachment" not in content_disposition:
                try:
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset()
                    html = payload.decode(charset if charset else 'utf-8', errors='replace')
                    html = re.sub(r'<(br|p|/p|/div)>', '\n', html, flags=re.IGNORECASE)
                    content += re.sub('<[^<]+?>', '', html)
                except:
                    pass
    else:
        try:
            payload = msg.get_payload(decode=True)
            charset = msg.get_content_charset()
            content = payload.decode(charset if charset else 'utf-8', errors='replace')
        except:
            pass
    return content


def parse_spoke_line(line):
    """Parse spoke statistics line."""
    match = re.search(r'租户:\s*([^,]+),\s*设备:\s*([^,]+),\s*留意:\s*(.+)', line)
    if match:
        return {
            "tenant": match.group(1).strip(),
            "device": match.group(2).strip(),
            "details": match.group(3).strip()
        }
    return None


def extract_granular_spoke_stats(content):
    """Extract detailed spoke statistics from email content."""
    detailed_stats = {"special": [], "general": [], "skipped": []}
    lines = content.split('\n')
    current_section = None
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if "--- 特殊spOke统计汇总 ---" in line:
            current_section = "special"
            continue
        elif "--- 一般留意spOke统计汇总 ---" in line:
            current_section = "general"
            continue
        elif "--- 根据 escfaultspecial.json 跳过的spOke ---" in line:
            current_section = "skipped"
            continue
        elif "==================================================" in line:
            current_section = None
            continue

        if current_section in ["special", "general"]:
            parsed = parse_spoke_line(line)
            if parsed:
                detailed_stats[current_section].append(parsed)
        elif current_section == "skipped":
            m = re.search(r'租户:\s*([^,]+),\s*设备:\s*([^\s(]+)', line)
            if m:
                detailed_stats["skipped"].append({
                    "tenant": m.group(1).strip(),
                    "device": m.group(2).strip(),
                    "details": "Skipped"
                })
    return detailed_stats


def extract_alert_info(content):
    """Extract device info from Alert emails (CRITICAL alerts with UNREACHABLE status).
    
    Returns dict with:
    - devices: list of unreachable/offline devices
    - has_unreachable: bool indicating if any device is unreachable
    """
    # Clean HTML tags
    text = re.sub(r'<[^>]+>', ' ', content)
    text = re.sub(r'\s+', ' ', text).strip()
    
    devices = []
    
    # Extract device name from "Device : xxx" pattern
    device_match = re.search(r'Device\s*:\s*([^\s<]+)', text)
    tenant_match = re.search(r'Tenant\s*:\s*([^\s<]+)', text)
    desc_match = re.search(r'Descriptions?\s*:\s*([^\n<]+)', text)
    
    if device_match:
        device_name = device_match.group(1).strip()
        tenant = tenant_match.group(1).strip() if tenant_match else "Unknown"
        description = desc_match.group(1).strip() if desc_match else ""
        
        # Check for UNREACHABLE/offline status
        is_unreachable = 'UNREACHABLE' in text.upper() or '失联' in text or 'offline' in text.lower()
        status = "失联" if is_unreachable else "告警"
        
        devices.append({
            "device": device_name,
            "tenant": tenant,
            "details": description if description else status,
            "status": "unreachable" if is_unreachable else "alert"
        })
    
    return {
        "devices": devices,
        "has_unreachable": any(d["status"] == "unreachable" for d in devices)
    }


def find_workspace():
    """Find the correct workspace directory."""
    # Priority:
    # 1. WORKSPACE_DIR environment variable (explicit override)
    # 2. Search for agents/*/workspace/memory/email_credentials.json
    # 3. Fallback to script's parent directory
    
    env_workspace = os.environ.get('WORKSPACE_DIR')
    if env_workspace and os.path.isdir(env_workspace):
        # Verify config exists
        config_path = os.path.join(env_workspace, 'memory', 'email_credentials.json')
        if os.path.isfile(config_path):
            return env_workspace
    
    script_path = os.path.abspath(__file__)
    
    # Search for agents/*/workspace with email_credentials.json
    # Start from script location and go up
    search_paths = [
        os.path.dirname(script_path),  # skills/rpctvm
        os.path.dirname(os.path.dirname(script_path)),  # skills
        os.path.dirname(os.path.dirname(os.path.dirname(script_path))),  # workspace
    ]
    
    for base_path in search_paths:
        # Check if we're under openclaw
        openclaw_idx = base_path.find('/.openclaw/')
        if openclaw_idx > 0:
            openclaw_root = base_path[:openclaw_idx + len('/.openclaw')]
            agents_dir = os.path.join(openclaw_root, 'agents')
            if os.path.isdir(agents_dir):
                for agent in os.listdir(agents_dir):
                    agent_workspace = os.path.join(agents_dir, agent, 'workspace')
                    config_path = os.path.join(agent_workspace, 'memory', 'email_credentials.json')
                    if os.path.isfile(config_path):
                        return agent_workspace
    
    # Fallback: check relative paths
    candidate = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(script_path))), 
                             'agents', 'vegetablesoup', 'workspace')
    config_path = os.path.join(candidate, 'memory', 'email_credentials.json')
    if os.path.isfile(config_path):
        return candidate
    
    # Final fallback
    return os.path.dirname(os.path.dirname(os.path.dirname(script_path)))


def load_config():
    """Load configuration from environment or config file."""
    workspace = find_workspace()
    
    config_path = os.environ.get(
        'EMAIL_CONFIG_PATH',
        os.path.join(workspace, 'memory', 'email_credentials.json')
    )
    
    with open(config_path, 'r') as f:
        return json.load(f)


def summarize_sent():
    """Main function to summarize sent emails."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=1, help="Number of days to search back (default: 1 = 24 hours)")
    parser.add_argument("--config", type=str, help="Path to config file (overrides EMAIL_CONFIG_PATH)")
    args = parser.parse_args()

    # Load configuration
    if args.config:
        with open(args.config, 'r') as f:
            config = json.load(f)
    else:
        config = load_config()

    # Get target recipient from environment or config
    target_recipient = os.environ.get(
        'TARGET_RECIPIENT',
        config.get('target_recipient', '')
    )
    
    if not target_recipient:
        print("Error: No target recipient configured. Set TARGET_RECIPIENT env var or config.")
        return

    sent_folder = "&XfJT0ZAB-"  # IMAP UTF-7 for "已发送"
    
    # Calculate cutoff time (北京时间 Asia/Shanghai)
    # 日报使用固定日期窗口：昨天 00:00 开始
    # 这样确保昨天 08:xx 的巡检邮件不会被滑动窗口遗漏
    cst = timezone(timedelta(hours=8))
    now = datetime.now(cst)
    if args.days == 1:
        # 日报：从昨天 00:00 开始
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff_date = today_start - timedelta(days=1)  # 昨天 00:00
    else:
        # 周报等：使用滑动窗口
        cutoff_date = now - timedelta(days=args.days)

    try:
        # Connect to IMAP server
        # Use SSL for port 993, plain for port 143
        imap_port = config.get('imap_port', 143)
        if imap_port == 993:
            mail = imaplib.IMAP4_SSL(config['imap_server'], imap_port)
        else:
            mail = imaplib.IMAP4(config['imap_server'], imap_port)
        mail.login(config['email'], config['auth_code'])
        
        # Critical: Send ID command for 163.com mailbox
        imaplib.Commands['ID'] = ('AUTH')
        mail._simple_command('ID', '("name" "openclaw" "version" "1.0.0")')
        
        mail.select(sent_folder)
        
        # Use SINCE filter to limit search range (avoids timeout on large mailboxes)
        # 163邮箱按本地时间处理，日期应为北京时间
        # 日报：从昨天开始；周报等：从 N 天前开始
        since_date = cutoff_date.strftime('%d-%b-%Y')
        status, messages = mail.search(None, f'SINCE {since_date}')
        email_ids = messages[0].split()
        
        report_data = []
        # Pull enough emails to cover the time range (batch fetch)
        scan_limit = 200 if args.days <= 1 else 1000
        start_idx = len(email_ids) - 1
        end_idx = max(-1, len(email_ids) - scan_limit - 1)
        
        for i in range(start_idx, end_idx, -1):
            try:
                res, msg_data = mail.fetch(email_ids[i], "(BODY[HEADER.FIELDS (TO CC BCC SUBJECT DATE)])")
                header_msg = email.message_from_bytes(msg_data[0][1])
            except Exception as e:
                print(f"Warning: Failed to fetch header for email {i}: {e}")
                continue
            
            # Check Date first
            date_raw = header_msg.get("Date")
            try:
                msg_date = email.utils.parsedate_to_datetime(date_raw)
                if msg_date < cutoff_date:
                    continue  # Skip old emails, don't break - newer emails might be after this
            except:
                continue

            to_field = str(header_msg.get("To", "")).lower()
            cc_field = str(header_msg.get("Cc", "")).lower()
            bcc_field = str(header_msg.get("Bcc", "")).lower()
            
            # Check if target recipient is in TO, CC, or BCC
            if target_recipient.lower() in (to_field + cc_field + bcc_field):
                try:
                    res_full, msg_full_data = mail.fetch(email_ids[i], "(RFC822)")
                    msg_full = email.message_from_bytes(msg_full_data[0][1])
                except Exception as e:
                    print(f"Warning: Failed to fetch full email {i}: {e}")
                    continue
                
                subject, encoding = decode_header(msg_full["Subject"])[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding if encoding else "utf-8", errors='replace')
                
                content = get_email_content(msg_full)
                is_proximity = "Tunnel Effective Proximity" in subject
                is_alert = "CRITICAL" in subject.upper() or "CRITICAL" in content.upper()
                
                if is_proximity:
                    stats = extract_granular_spoke_stats(content)
                    report_data.append({
                        "date": date_raw,
                        "subject": subject,
                        "type": "Proximity",
                        "granular_spoke_stats": stats,
                        "critical_alert": None
                    })
                elif is_alert:
                    # Extract device info from Alert emails
                    alert_info = extract_alert_info(content)
                    report_data.append({
                        "date": date_raw,
                        "subject": subject,
                        "type": "Alert",
                        "granular_spoke_stats": None,
                        "alert_devices": alert_info["devices"],
                        "has_unreachable": alert_info["has_unreachable"]
                    })

        mail.logout()
        
        # Output path from environment or default
        workspace = find_workspace()
        output_path = os.environ.get(
            'OUTPUT_PATH',
            os.path.join(workspace, 'memory', 'sent_emails_data.json')
        )
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        print(f"Processed {len(report_data)} emails for last {args.days} day(s).")
        
    except Exception as e:
        print(f"Error: {str(e)}")


if __name__ == "__main__":
    summarize_sent()