#!/usr/bin/env python3
"""
Sync email report data to Feishu Bitable

Reads sent_emails_data.json and syncs to the daily summary table.
Handles deduplication and merging of same-day records.

Usage:
    python sync_to_bitable.py
    python sync_to_bitable.py --backfill  # Backfill all historical data
"""

import os
import json
import argparse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

# Import from skill directory
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def parse_date(date_str):
    """Parse email date string to datetime."""
    try:
        return parsedate_to_datetime(date_str)
    except:
        return None


def date_to_timestamp_ms(dt):
    """Convert datetime to milliseconds timestamp for Feishu."""
    return int(dt.timestamp() * 1000)


def load_email_data():
    """Load email data from JSON file."""
    data_path = os.environ.get(
        'OUTPUT_PATH',
        '/root/.openclaw/agents/rpctvm/workspace/memory/sent_emails_data.json'
    )
    
    if not os.path.exists(data_path):
        print(f"Error: Data file not found: {data_path}")
        return []
    
    with open(data_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def aggregate_by_date(emails):
    """Aggregate emails by date, merging device lists."""
    daily_data = {}
    
    for email in emails:
        dt = parse_date(email.get("date", ""))
        if not dt:
            continue
        
        date_key = dt.date()
        date_str = dt.strftime("%Y-%m-%d")
        
        if date_key not in daily_data:
            daily_data[date_key] = {
                "date": date_str,
                "count": 0,
                "special_devices": {},  # Dedupe by device name
                "general_devices": {},
                "timestamp_ms": date_to_timestamp_ms(dt.replace(hour=0, minute=0, second=0))
            }
        
        daily_data[date_key]["count"] += 1
        
        # Merge devices with deduplication
        stats = email.get("granular_spoke_stats", {})
        if stats:
            for dev in stats.get("special", []):
                device_name = dev.get("device", "")
                if device_name and device_name not in daily_data[date_key]["special_devices"]:
                    daily_data[date_key]["special_devices"][device_name] = dev.get("details", "")
            
            for dev in stats.get("general", []):
                device_name = dev.get("device", "")
                if device_name and device_name not in daily_data[date_key]["general_devices"]:
                    daily_data[date_key]["general_devices"][device_name] = dev.get("details", "")
    
    return daily_data


def format_device_details(daily_record):
    """Format device details for Bitable field."""
    parts = []
    
    # Special devices first
    for name, details in daily_record["special_devices"].items():
        parts.append(f"[特殊] {name} ({details})")
    
    # Then general devices
    for name, details in daily_record["general_devices"].items():
        parts.append(f"{name} ({details})")
    
    return ", ".join(parts) if parts else ""


def create_bitable_record(daily_record, app_token, table_id):
    """Create a record in Feishu Bitable via API."""
    import urllib.request
    import urllib.error
    
    # Format device details
    device_details = format_device_details(daily_record)
    
    # Prepare record fields
    fields = {
        "日期": daily_record["timestamp_ms"],
        "租户": "浦发",
        "邮件数": str(daily_record["count"]),
        "特殊设备数": str(len(daily_record["special_devices"])),
        "一般关注设备数": str(len(daily_record["general_devices"])),
        "设备详情": device_details
    }
    
    print(f"Creating record for {daily_record['date']}: {daily_record['count']} emails, "
          f"{len(daily_record['special_devices'])} special, {len(daily_record['general_devices'])} general")
    
    # Note: The actual API call should be done by the agent using feishu_bitable_create_record
    # This function returns the fields dict for the agent to use
    return fields


def main():
    parser = argparse.ArgumentParser(description="Sync email data to Feishu Bitable")
    parser.add_argument("--backfill", action="store_true", help="Backfill all historical data")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be synced without actually doing it")
    args = parser.parse_args()
    
    # Load configuration
    bitable_config_path = os.environ.get(
        'BITABLE_CONFIG_PATH',
        '/root/.openclaw/workspace/memory/rpctvm_bitable.json'
    )
    
    with open(bitable_config_path, 'r') as f:
        bitable_config = json.load(f)
    
    app_token = bitable_config['app_token']
    table_id = bitable_config['table_id']
    
    print(f"Bitable: app_token={app_token}, table_id={table_id}")
    
    # Load email data
    emails = load_email_data()
    if not emails:
        print("No email data found")
        return
    
    print(f"Loaded {len(emails)} emails")
    
    # Aggregate by date
    daily_data = aggregate_by_date(emails)
    print(f"Aggregated into {len(daily_data)} days")
    
    # Sort by date (newest first)
    sorted_dates = sorted(daily_data.keys(), reverse=True)
    
    if args.dry_run:
        print("\n=== DRY RUN - Would sync the following records ===")
        for date_key in sorted_dates:
            record = daily_data[date_key]
            print(f"\n{record['date']}:")
            print(f"  Emails: {record['count']}")
            print(f"  Special: {len(record['special_devices'])} - {list(record['special_devices'].keys())}")
            print(f"  General: {len(record['general_devices'])} - {list(record['general_devices'].keys())}")
            print(f"  Details: {format_device_details(record)[:100]}...")
        return
    
    # Output records as JSON for agent to process
    records_to_sync = []
    for date_key in sorted_dates:
        record = daily_data[date_key]
        fields = {
            "日期": record["timestamp_ms"],
            "租户": "浦发",
            "邮件数": str(record["count"]),
            "特殊设备数": str(len(record["special_devices"])),
            "一般关注设备数": str(len(record["general_devices"])),
            "设备详情": format_device_details(record)
        }
        records_to_sync.append({
            "date": record["date"],
            "fields": fields
        })
    
    # Output as JSON for agent
    output = {
        "app_token": app_token,
        "table_id": table_id,
        "records": records_to_sync
    }
    
    print("\n=== RECORDS TO SYNC ===")
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()