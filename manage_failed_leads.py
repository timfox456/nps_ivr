#!/usr/bin/env python3
"""
Utility script to view and retry failed lead submissions.

Usage:
    python manage_failed_leads.py list              # List all failed leads
    python manage_failed_leads.py retry <id>        # Retry a specific failed lead
    python manage_failed_leads.py retry-all         # Retry all unresolved failed leads
"""
import sys
import asyncio
from app.db import SessionLocal
from app.models import FailedLead
from app.salesforce import create_lead
from datetime import datetime


def list_failed_leads():
    """List all failed leads"""
    db = SessionLocal()
    try:
        leads = db.query(FailedLead).filter(FailedLead.resolved == 0).order_by(FailedLead.created_at.desc()).all()

        if not leads:
            print("✓ No failed leads found!")
            return

        print(f"\n{'='*80}")
        print(f"Found {len(leads)} failed lead(s):")
        print(f"{'='*80}\n")

        for lead in leads:
            print(f"ID: {lead.id}")
            print(f"Created: {lead.created_at}")
            print(f"Channel: {lead.channel}")
            print(f"Session ID: {lead.session_id}")
            print(f"Retry Count: {lead.retry_count}")
            print(f"Error: {lead.error_message}")
            print(f"Lead Data:")
            for key, value in lead.lead_data.items():
                if not key.startswith('_'):
                    print(f"  {key}: {value}")
            print(f"{'-'*80}\n")
    finally:
        db.close()


async def retry_lead(lead_id: int):
    """Retry submitting a specific failed lead"""
    db = SessionLocal()
    try:
        lead = db.query(FailedLead).filter(FailedLead.id == lead_id).first()

        if not lead:
            print(f"❌ Failed lead with ID {lead_id} not found")
            return False

        if lead.resolved:
            print(f"⚠️  Lead {lead_id} was already successfully submitted")
            return False

        print(f"Retrying lead {lead_id}...")
        print(f"Lead data: {lead.lead_data}")

        try:
            npa_response = await create_lead(lead.lead_data)

            # Mark as resolved
            lead.resolved = 1
            lead.retry_count += 1
            lead.last_retry_at = datetime.utcnow()

            # Save to succeeded_leads table for reconciliation
            from app.models import SucceededLead
            succeeded_lead = SucceededLead(
                lead_data=lead.lead_data,
                channel=lead.channel,
                session_id=lead.session_id,
                npa_response=npa_response if isinstance(npa_response, dict) else None
            )
            db.add(succeeded_lead)

            db.commit()

            print(f"✓ Successfully submitted lead {lead_id} to NPA API")
            return True

        except Exception as e:
            # Update retry count but keep as unresolved
            lead.retry_count += 1
            lead.last_retry_at = datetime.utcnow()
            lead.error_message = f"{lead.error_message}\n\nRetry {lead.retry_count} at {datetime.utcnow()}: {str(e)}"
            db.commit()

            print(f"❌ Failed to submit lead {lead_id}: {e}")
            return False

    finally:
        db.close()


async def retry_all_leads():
    """Retry all unresolved failed leads"""
    db = SessionLocal()
    try:
        leads = db.query(FailedLead).filter(FailedLead.resolved == 0).all()

        if not leads:
            print("✓ No failed leads to retry!")
            return

        print(f"\nRetrying {len(leads)} failed lead(s)...\n")

        success_count = 0
        fail_count = 0

        for lead in leads:
            result = await retry_lead(lead.id)
            if result:
                success_count += 1
            else:
                fail_count += 1

        print(f"\n{'='*80}")
        print(f"Summary: {success_count} succeeded, {fail_count} failed")
        print(f"{'='*80}\n")

    finally:
        db.close()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    if command == "list":
        list_failed_leads()

    elif command == "retry":
        if len(sys.argv) < 3:
            print("Error: Please provide a lead ID to retry")
            print("Usage: python manage_failed_leads.py retry <id>")
            sys.exit(1)

        lead_id = int(sys.argv[2])
        asyncio.run(retry_lead(lead_id))

    elif command == "retry-all":
        asyncio.run(retry_all_leads())

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
