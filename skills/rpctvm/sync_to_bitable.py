#!/usr/bin/env python3
"""
Sync email report data to Feishu Bitable

Reads sent_emails_data.json and syncs to the daily summary table.
Handles deduplication and merging of same-day records.

Usage:
    python sync_to_bitable.py
    python sync_to_bitable.py --backfill  # Backfill all historical data
    python sync_to_bitable.py --dry-run    # Show what would be synced
"""

import os
import sys
import json
import urllib.request
import urllib.error
import argparse
from datetime import datetime, timezone, timedelta, date as date_type
from email.utils import parsedate_to_datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# --- Feishu API helpers ---

def get_tenant_access_token(app_id: str, app_secret: str) -> str:
    """Get Feishu tenant access token."""
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    data = json.dumps({"app_id": app_id, "app_secret": app_secret}).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
        return result.get("tenant_access_token", "")


def list_bitable_records(app_token: str, table_id: str, token: str) -> list:
    """List all records in a Bitable table. Returns list of (record_id, date_ts) tuples."""
    records = []
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
    page_token = None
    while True:
        params = {"page_size": 500}
        if page_token:
            params["page_token"] = page_token
        req = urllib.request.Request(url + "?" + urllib.parse.urlencode(params))
        req.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
        if result.get("code") != 0:
            break
        for item in result["data"].get("items", []):
            date_val = item["fields"].get("日期")
            records.append((item["id"], date_val))
        if not result["data"].get("has_more"):
            break
        page_token = result["data"].get("page_token")
    return records


def create_bitable_record(app_token: str, table_id: str, token: str, fields: dict) -> str:
    """Create a record in Bitable. Returns record_id on success."""
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
    data = json.dumps({"fields": fields}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json; charset=utf-8")
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
    if result.get("code") != 0:
        raise Exception(f"Bitable create failed: {result}")
    return result["data"]["record"]["record_id"]


def delete_bitable_record(app_token: str, table_id: str, token: str, record_id: str):
    """Delete a record from Bitable."""
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}"
    req = urllib.request.Request(url, method="DELETE")
    req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


# --- Date helpers ---

def parse_date(date_str: str):
    """Parse email date string to datetime."""
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        return None


def date_to_timestamp_ms(dt: datetime) -> int:
    """Convert datetime to milliseconds timestamp (UTC midnight of the date in Beijing timezone)."""
    # Use date in Beijing timezone (UTC+8)
    # For a date, use UTC midnight that corresponds to Beijing 00:00
    # Beijing 00:00 = UTC previous day 16:00
    bj_date = dt.astimezone(timezone.utc).date()
    # UTC midnight for that date = Beijing 08:00 next day
    # We want Beijing 00:00 of the given date
    utc_dt = datetime(bj_date.year, bj_date.month, bj_date.day, 0, 0, 0, tzinfo=timezone.utc)
    # Convert to Beijing date equivalent - adjust for UTC offset
    # Actually: Beijing 00:00 = UTC prev_day 16:00
    bj_dt = datetime(bj_date.year, bj_date.month, bj_date.day, 0, 0, 0,
                      tzinfo=timezone(timedelta(hours=8)))
    utc_for_bj_midnight = bj_dt.astimezone(timezone.utc).replace(tzinfo=None)
    return int(utc_for_bj_midnight.timestamp() * 1000)


# --- Data processing ---

def load_email_data():
    """Load email data from JSON file."""
    data_path = os.environ.get(
        "OUTPUT_PATH",
        "/root/.openclaw/agents/vegetablesoup/workspace/memory/sent_emails_data.json"
    )
    if not os.path.exists(data_path):
        print(f"Error: Data file not found: {data_path}")
        return []
    with open(data_path, "r", encoding="utf-8") as f:
        return json.load(f)


def aggregate_by_date(emails: list) -> dict:
    """Aggregate emails by date, merging device lists (Beijing date)."""
    daily_data = {}
    today_bj = datetime.now(timezone(timedelta(hours=8))).date()

    for email in emails:
        dt = parse_date(email.get("date", ""))
        if not dt:
            continue

        # Convert to Beijing time
        bj_dt = dt.astimezone(timezone(timedelta(hours=8)))
        date_key = bj_dt.date()
        date_str = bj_dt.strftime("%Y-%m-%d")

        if date_key not in daily_data:
            daily_data[date_key] = {
                "date": date_str,
                "count": 0,
                "special_devices": {},
                "general_devices": {},
                "timestamp_ms": date_to_timestamp_ms(bj_dt)
            }

        daily_data[date_key]["count"] += 1

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


def format_device_details(daily_record: dict) -> str:
    """Format device details for Bitable field."""
    parts = []
    for name, details in daily_record["special_devices"].items():
        clean = details.replace("</span>", "").replace("</p>", "").replace("'", "").strip()
        parts.append(f"[特殊] {name} ({clean})")
    for name, details in daily_record["general_devices"].items():
        clean = details.replace("</span>", "").replace("</p>", "").replace("'", "").strip()
        parts.append(f"{name} ({clean})")
    return "；".join(parts) if parts else ""


def main():
    parser = argparse.ArgumentParser(description="Sync email data to Feishu Bitable")
    parser.add_argument("--backfill", action="store_true", help="Backfill all historical data")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be synced")
    parser.add_argument("--days", type=int, default=1, help="Number of past days to sync (default: 1)")
    args = parser.parse_args()

    # Determine which dates to sync
    today_bj = datetime.now(timezone(timedelta(hours=8))).date()
    cutoff = today_bj - timedelta(days=args.days)

    # Load configuration
    bitable_config_path = os.environ.get(
        "BITABLE_CONFIG_PATH",
        "/root/.openclaw/agents/vegetablesoup/workspace/memory/rpctvm_bitable.json"
    )
    with open(bitable_config_path, "r") as f:
        bitable_config = json.load(f)

    app_token = bitable_config["app_token"]
    table_id = bitable_config["table_id"]

    # Get Feishu credentials
    email_config_path = os.environ.get(
        "EMAIL_CONFIG_PATH",
        "/root/.openclaw/agents/vegetablesoup/workspace/memory/email_credentials.json"
    )
    with open(email_config_path, "r") as f:
        email_config = json.load(f)

    app_id = os.environ.get("FEISHU_APP_ID", "cli_a90466cb86f85bc8")
    app_secret = os.environ.get("FEISHU_APP_SECRET", email_config.get("app_secret", ""))

    if not app_secret:
        print("Error: FEISHU_APP_SECRET not set")
        sys.exit(1)

    print(f"Bitable: {app_token} / {table_id}")

    # Get token
    token = get_tenant_access_token(app_id, app_secret)
    print(f"Got tenant token: {token[:20]}...")

    # Get existing records
    existing = list_bitable_records(app_token, table_id, token)
    existing_dates = set()
    for _, date_ts in existing:
        if date_ts:
            # Convert ms timestamp to date
            d = datetime.fromtimestamp(date_ts / 1000, tz=timezone(timedelta(hours=8))).date()
            existing_dates.add(d)
    print(f"Existing records: {len(existing)}, dates: {sorted(existing_dates)}")

    # Load email data
    emails = load_email_data()
    if not emails:
        print("No email data found")
        return

    print(f"Loaded {len(emails)} emails")

    # Aggregate by date
    daily_data = aggregate_by_date(emails)
    print(f"Aggregated into {len(daily_data)} days: {list(daily_data.keys())}")

    # Determine which dates to sync
    today_bj = datetime.now(timezone(timedelta(hours=8))).date()
    cutoff = today_bj - timedelta(days=args.days)

    # Sort by date (newest first)
    sorted_dates = sorted(daily_data.keys(), reverse=True)

    if args.dry_run:
        print("\n=== DRY RUN - Would sync the following records ===")
        for date_key in sorted_dates:
            if date_key >= cutoff and not args.backfill:
                print(f"  [SKIP] {date_key} (within {args.days} day(s) or today)")
                continue
            if date_key in existing_dates and not args.backfill:
                print(f"  [SKIP] {date_key} (already exists)")
                continue
            record = daily_data[date_key]
            print(f"\n{record['date']}:")
            print(f"  Emails: {record['count']}")
            print(f"  Special: {len(record['special_devices'])}")
            print(f"  General: {len(record['general_devices'])}")
            print(f"  Details: {format_device_details(record)[:100]}")
        return

    # Sync
    synced = 0
    for date_key in sorted_dates:
        if date_key > cutoff and not args.backfill:
            print(f"  [SKIP] {date_key} (within {args.days} day(s) or today)")
            continue
        if date_key in existing_dates and not args.backfill:
            print(f"  [SKIP] {date_key} (already exists)")
            continue

        record = daily_data[date_key]
        fields = {
            "日期": record["timestamp_ms"],
            "租户": "浦发",
            "邮件数": record["count"],
            "特殊设备数": len(record["special_devices"]),
            "一般关注设备数": len(record["general_devices"]),
            "设备详情": format_device_details(record)
        }

        try:
            rid = create_bitable_record(app_token, table_id, token, fields)
            print(f"  [OK] {record['date']}: created record {rid}")
            synced += 1
        except Exception as e:
            print(f"  [FAIL] {record['date']}: {e}")

    print(f"\nDone. Synced {synced} records.")


if __name__ == "__main__":
    main()
