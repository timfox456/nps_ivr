#!/usr/bin/env python3
"""
View rejected leads from the database.

Rejected leads are leads that failed business validation rules
(e.g., Alaska/Hawaii ZIP codes, old vehicles, electric motorcycles, Slingshots).
These are different from failed_leads which are API submission failures.
"""
import argparse
from datetime import datetime, timedelta
from app.db import SessionLocal
from app.models import RejectedLead


def parse_time_filter(time_str: str) -> datetime:
    """Parse time filter like '24h', '7d', '30d' into datetime"""
    if time_str.endswith('h'):
        hours = int(time_str[:-1])
        return datetime.utcnow() - timedelta(hours=hours)
    elif time_str.endswith('d'):
        days = int(time_str[:-1])
        return datetime.utcnow() - timedelta(days=days)
    else:
        raise ValueError(f"Invalid time format: {time_str}. Use format like '24h' or '7d'")


def main():
    parser = argparse.ArgumentParser(description='View rejected leads')
    parser.add_argument('--since', help='Time filter (e.g., 24h, 7d, 30d)', default=None)
    parser.add_argument('--channel', help='Filter by channel (sms or voice)', choices=['sms', 'voice'], default=None)
    parser.add_argument('--category', help='Filter by rejection category',
                        choices=['zip_code', 'vehicle_age', 'electric', 'slingshot'], default=None)
    parser.add_argument('--export', help='Export to CSV', choices=['csv'], default=None)
    parser.add_argument('--stats', help='Show statistics summary', action='store_true')
    args = parser.parse_args()

    db = SessionLocal()
    try:
        # Build query
        query = db.query(RejectedLead)

        # Apply filters
        if args.since:
            since_time = parse_time_filter(args.since)
            query = query.filter(RejectedLead.rejected_at >= since_time)

        if args.channel:
            query = query.filter(RejectedLead.channel == args.channel)

        if args.category:
            query = query.filter(RejectedLead.rejection_category == args.category)

        # Order by most recent first
        query = query.order_by(RejectedLead.rejected_at.desc())

        rejected_leads = query.all()

        if not rejected_leads:
            print("No rejected leads found.")
            return

        # Show statistics if requested
        if args.stats:
            print("\n=== REJECTED LEADS STATISTICS ===\n")

            # Total count
            print(f"Total rejected leads: {len(rejected_leads)}")

            # By channel
            sms_count = sum(1 for lead in rejected_leads if lead.channel == 'sms')
            voice_count = sum(1 for lead in rejected_leads if lead.channel == 'voice')
            print(f"\nBy Channel:")
            print(f"  SMS:   {sms_count} ({sms_count/len(rejected_leads)*100:.1f}%)")
            print(f"  Voice: {voice_count} ({voice_count/len(rejected_leads)*100:.1f}%)")

            # By category
            categories = {}
            for lead in rejected_leads:
                cat = lead.rejection_category
                categories[cat] = categories.get(cat, 0) + 1

            print(f"\nBy Rejection Category:")
            for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
                print(f"  {cat:15} {count:4} ({count/len(rejected_leads)*100:.1f}%)")

            print("\n" + "="*40 + "\n")

        # Export to CSV if requested
        if args.export == 'csv':
            import csv
            filename = f"rejected_leads_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'id', 'rejected_at', 'channel', 'rejection_category', 'rejection_reason',
                    'full_name', 'zip_code', 'phone', 'email',
                    'vehicle_year', 'vehicle_make', 'vehicle_model', 'session_id'
                ])

                for lead in rejected_leads:
                    data = lead.lead_data
                    writer.writerow([
                        lead.id,
                        lead.rejected_at.strftime('%Y-%m-%d %H:%M:%S'),
                        lead.channel,
                        lead.rejection_category,
                        lead.rejection_reason,
                        data.get('full_name', ''),
                        data.get('zip_code', ''),
                        data.get('phone', ''),
                        data.get('email', ''),
                        data.get('vehicle_year', ''),
                        data.get('vehicle_make', ''),
                        data.get('vehicle_model', ''),
                        lead.session_id
                    ])

            print(f"Exported {len(rejected_leads)} rejected leads to {filename}")
            return

        # Display leads
        print(f"\n=== REJECTED LEADS ({len(rejected_leads)} total) ===\n")

        for lead in rejected_leads:
            print(f"ID: {lead.id}")
            print(f"Rejected At: {lead.rejected_at.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Channel: {lead.channel.upper()}")
            print(f"Category: {lead.rejection_category}")
            print(f"Reason: {lead.rejection_reason}")
            print(f"Session ID: {lead.session_id}")

            # Display lead data
            data = lead.lead_data
            print(f"\nLead Data:")
            print(f"  Name:    {data.get('full_name', 'N/A')}")
            print(f"  ZIP:     {data.get('zip_code', 'N/A')}")
            print(f"  Phone:   {data.get('phone', 'N/A')}")
            print(f"  Email:   {data.get('email', 'N/A')}")
            print(f"  Vehicle: {data.get('vehicle_year', 'N/A')} {data.get('vehicle_make', 'N/A')} {data.get('vehicle_model', 'N/A')}")

            print("\n" + "-"*60 + "\n")

    finally:
        db.close()


if __name__ == '__main__':
    main()
