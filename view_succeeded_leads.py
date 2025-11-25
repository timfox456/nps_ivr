#!/usr/bin/env python3
"""
Utility script to view successfully submitted leads for reconciliation with NPA API.

Usage:
    python view_succeeded_leads.py                 # View all succeeded leads
    python view_succeeded_leads.py --since 24h     # View leads from last 24 hours
    python view_succeeded_leads.py --since 7d      # View leads from last 7 days
    python view_succeeded_leads.py --channel sms   # View only SMS leads
    python view_succeeded_leads.py --export csv    # Export to CSV
"""
import sys
import csv
from datetime import datetime, timedelta
from app.db import SessionLocal
from app.models import SucceededLead


def parse_time_delta(time_str: str) -> timedelta:
    """Parse time string like '24h', '7d' into timedelta"""
    if not time_str:
        return None

    unit = time_str[-1]
    value = int(time_str[:-1])

    if unit == 'h':
        return timedelta(hours=value)
    elif unit == 'd':
        return timedelta(days=value)
    elif unit == 'w':
        return timedelta(weeks=value)
    else:
        raise ValueError(f"Unknown time unit: {unit}. Use 'h' (hours), 'd' (days), or 'w' (weeks)")


def list_succeeded_leads(since: str = None, channel: str = None, export_format: str = None):
    """List succeeded leads with optional filters"""
    db = SessionLocal()
    try:
        query = db.query(SucceededLead).order_by(SucceededLead.submitted_at.desc())

        # Apply filters
        if since:
            time_delta = parse_time_delta(since)
            cutoff_time = datetime.utcnow() - time_delta
            query = query.filter(SucceededLead.submitted_at >= cutoff_time)

        if channel:
            query = query.filter(SucceededLead.channel == channel)

        leads = query.all()

        if not leads:
            print("✓ No succeeded leads found!")
            return

        # Export to CSV
        if export_format == 'csv':
            filename = f"succeeded_leads_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            with open(filename, 'w', newline='') as csvfile:
                fieldnames = ['id', 'submitted_at', 'channel', 'session_id',
                             'full_name', 'phone', 'email', 'zip_code',
                             'vehicle_make', 'vehicle_model', 'vehicle_year']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                writer.writeheader()
                for lead in leads:
                    row = {
                        'id': lead.id,
                        'submitted_at': lead.submitted_at,
                        'channel': lead.channel,
                        'session_id': lead.session_id,
                        'full_name': lead.lead_data.get('full_name', ''),
                        'phone': lead.lead_data.get('phone', ''),
                        'email': lead.lead_data.get('email', ''),
                        'zip_code': lead.lead_data.get('zip_code', ''),
                        'vehicle_make': lead.lead_data.get('vehicle_make', ''),
                        'vehicle_model': lead.lead_data.get('vehicle_model', ''),
                        'vehicle_year': lead.lead_data.get('vehicle_year', ''),
                    }
                    writer.writerow(row)

            print(f"✓ Exported {len(leads)} leads to {filename}")
            return

        # Display in terminal
        print(f"\n{'='*80}")
        print(f"Found {len(leads)} succeeded lead(s):")
        print(f"{'='*80}\n")

        for lead in leads:
            print(f"ID: {lead.id}")
            print(f"Submitted: {lead.submitted_at}")
            print(f"Channel: {lead.channel}")
            print(f"Session ID: {lead.session_id}")
            print(f"Lead Data:")
            for key, value in lead.lead_data.items():
                if not key.startswith('_'):
                    print(f"  {key}: {value}")

            if lead.npa_response:
                print(f"NPA Response:")
                for key, value in lead.npa_response.items():
                    print(f"  {key}: {value}")

            print(f"{'-'*80}\n")
    finally:
        db.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="View successfully submitted leads")
    parser.add_argument('--since', help='Time window (e.g., 24h, 7d, 4w)')
    parser.add_argument('--channel', choices=['sms', 'voice'], help='Filter by channel')
    parser.add_argument('--export', choices=['csv'], help='Export format')

    args = parser.parse_args()

    list_succeeded_leads(since=args.since, channel=args.channel, export_format=args.export)


if __name__ == "__main__":
    main()
