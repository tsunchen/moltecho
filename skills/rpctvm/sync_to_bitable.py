#!/usr/bin/env python3
"""
Sync email report data to Feishu Bitable

Reads sent_emails_data.json and syncs to the daily summary table.
Handles deduplication and merging of same-day records.

Usage:
    python sync_to_bitable.py --days 7        # sync past 7 days (default for weekly report)
    python sync_to_bitable.py --backfill      # backfill all historical data
    python sync_to_bitable.py --dry-run        # show what would be synced
"""

import os
import sys
import json
import urllib.request
import urllib.error
import urllib.parse
import argparse
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def get_tenant_access_token(app_id: str, app_secret: str) -> str:
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    data = json.dumps({"app_id": app_id, "app_secret": app_secret}).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
        return result.get("tenant_access_token", "")


def list_bitable_records(app_token: str, table_id: str, token: str) -> list:
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


def parse_date(date_str: str):
    from email.utils import parsedate_to_datetime
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        return None


def date_to_timestamp_ms(dt: datetime) -> int:
    bj_dt = dt.astimezone(timezone(timedelta(hours=8)))
    utc_dt = bj_dt.replace(tzinfo=None) - timedelta(hours=8)
    return int(utc_dt.timestamp() * 1000)


def load_email_data():
    data_path = os.environ.get(
        "OUTPUT_PATH",
        "{workspace}/memory/sent_emails_data.json"
    )
    if not os.path.exists(data_path):
        print(f"Error: Data file not found: {data_path}")
        return []
    with open(data_path, "r", encoding="utf-8") as f:
        return json.load(f)


def aggregate_by_date(emails: list) -> dict:
    daily_data = {}
    for email in emails:
        dt = parse_date(email.get("date", ""))
        if not dt:
            continue
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
                name = dev.get("device", "")
                if name and name not in daily_data[date_key]["special_devices"]:
                    daily_data[date_key]["special_devices"][name] = dev.get("details", "")
            for dev in stats.get("general", []):
                name = dev.get("device", "")
                if name and name not in daily_data[date_key]["general_devices"]:
                    daily_data[date_key]["general_devices"][name] = dev.get("details", "")
    return daily_data


def format_device_details(daily_record: dict) -> str:
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
    parser.add_argument("--backfill", action="store_true", help="Backfill ALL historical data")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be synced")
    parser.add_argument("--days", type=int, default=7, help="Number of past days to sync (default: 7)")
    args = parser.parse_args()

    # Load config
    creds_path = "{workspace}/memory/feishu_credentials.json"
    bitable_path = os.environ.get(
        "BITABLE_CONFIG_PATH",
        "{workspace}/memory/rpctvm_bitable.json"
    )
    with open(bitable_path, "r") as f:
        bitable_config = json.load(f)
    app_token = bitable_config["app_token"]
    table_id = bitable_config["table_id"]

    creds = {}
    if os.path.exists(creds_path):
        with open(creds_path) as f:
            creds = json.load(f)
    app_id = os.environ.get("FEISHU_APP_ID") or creds.get("app_id")
    app_secret = os.environ.get("FEISHU_APP_SECRET") or creds.get("app_secret")
    if not app_id or not app_secret:
        print("Error: FEISHU_APP_ID and FEISHU_APP_SECRET must be set (env or credentials file)")
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
            d = datetime.fromtimestamp(date_ts / 1000, tz=timezone(timedelta(hours=8))).date()
            existing_dates.add(d)
    print(f"Existing records: {len(existing)}, dates: {sorted(existing_dates)}")

    # Load email data
    emails = load_email_data()
    if not emails:
        print("No email data found")
        return
    print(f"Loaded {len(emails)} emails")

    # Aggregate
    daily_data = aggregate_by_date(emails)
    print(f"Aggregated: {list(daily_data.keys())}")

    today_bj = datetime.now(timezone(timedelta(hours=8))).date()
    cutoff = today_bj - timedelta(days=args.days)

    sorted_dates = sorted(daily_data.keys(), reverse=True)

    if args.dry_run:
        print(f"\n=== DRY RUN (days={args.days}, cutoff={cutoff}) ===")
        for date_key in sorted_dates:
            if date_key >= today_bj:
                print(f"  [SKIP] {date_key} (today)")
                continue
            if date_key in existing_dates:
                print(f"  [SKIP] {date_key} (already synced)")
                continue
            if date_key < cutoff:
                print(f"  [SKIP] {date_key} (older than cutoff={cutoff})")
                continue
            record = daily_data[date_key]
            print(f"\n  {record['date']}: {record['count']} emails, "
                  f"{len(record['special_devices'])} special, {len(record['general_devices'])} general")
        return

    # Sync
    synced = 0
    for date_key in sorted_dates:
        if date_key >= today_bj:
            print(f"  [SKIP] {date_key} (today)")
            continue
        if date_key in existing_dates:
            print(f"  [SKIP] {date_key} (already synced)")
            continue
        if date_key < cutoff:
            print(f"  [SKIP] {date_key} (older than cutoff={cutoff})")
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
            print(f"  [OK] {record['date']}: record {rid}")
            synced += 1
        except Exception as e:
            print(f"  [FAIL] {record['date']}: {e}")
    print(f"\nDone. Synced {synced} records.")


if __name__ == "__main__":
    main()
