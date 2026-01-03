#!/usr/bin/env python3
"""
Utility script to reconcile succeeded leads in our database with leads in NPA API.

This helps identify discrepancies where:
- Leads we think we submitted don't exist in NPA API
- Leads exist in NPA API that we don't have records of
- Lead data differs between our records and NPA API

Usage:
    python reconcile_leads.py                      # Check all succeeded leads
    python reconcile_leads.py --since 24h          # Check leads from last 24 hours
    python reconcile_leads.py --channel sms        # Check only SMS leads
"""
import sys
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


def reconcile_leads(since: str = None, channel: str = None):
    """Reconcile succeeded leads with NPA API"""
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
            print("✓ No succeeded leads found to reconcile!")
            return

        print(f"\n{'='*80}")
        print(f"Reconciling {len(leads)} succeeded lead(s) with NPA API...")
        print(f"{'='*80}\n")

        # TODO: Implement actual NPA API verification
        # For now, this is a placeholder that would need to:
        # 1. Query NPA API for leads by phone/email
        # 2. Compare data fields
        # 3. Report discrepancies

        print("NOTE: Full NPA API reconciliation not yet implemented.")
        print("This would require NPA API endpoints to:")
        print("  - Query leads by phone number or email")
        print("  - Return lead details for comparison")
        print()

        # For now, just show what we have in our database
        print("Succeeded leads in our database:")
        print(f"{'-'*80}")

        for lead in leads:
            print(f"ID: {lead.id} | Submitted: {lead.submitted_at} | Channel: {lead.channel}")
            print(f"  Phone: {lead.lead_data.get('phone', 'N/A')}")
            print(f"  Email: {lead.lead_data.get('email', 'N/A')}")
            print(f"  Vehicle: {lead.lead_data.get('vehicle_year', '')} "
                  f"{lead.lead_data.get('vehicle_make', '')} "
                  f"{lead.lead_data.get('vehicle_model', '')}")

            if lead.npa_response:
                print(f"  NPA Response: {lead.npa_response}")

            print()

        print(f"{'-'*80}")
        print(f"\nTotal: {len(leads)} succeeded lead(s)")
        print()
        print("To implement full reconciliation, the NPA API would need to provide:")
        print("  1. GET endpoint to query leads by phone/email")
        print("  2. Lead ID returned in submission response for direct lookup")
        print("  3. Webhook for lead status updates")

    finally:
        db.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Reconcile succeeded leads with NPA API")
    parser.add_argument('--since', help='Time window (e.g., 24h, 7d, 4w)')
    parser.add_argument('--channel', choices=['sms', 'voice'], help='Filter by channel')

    args = parser.parse_args()

    reconcile_leads(since=args.since, channel=args.channel)


if __name__ == "__main__":
    main()
