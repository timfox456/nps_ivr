#!/usr/bin/env python3
"""
Database migration to add rejected_leads table.

This creates the rejected_leads table for tracking leads that were rejected
by business rules (Alaska/Hawaii ZIP codes, old vehicles, electric bikes, Slingshots).
"""
from app.db import engine, Base
from app.models import RejectedLead


def main():
    print("Creating rejected_leads table...")

    # Create only the rejected_leads table
    RejectedLead.__table__.create(engine, checkfirst=True)

    print("✓ rejected_leads table created successfully!")
    print("\nYou can now view rejected leads with:")
    print("  python view_rejected_leads.py")
    print("  python view_rejected_leads.py --stats")
    print("  python view_rejected_leads.py --category vehicle_age")
    print("  python view_rejected_leads.py --export csv")


if __name__ == '__main__':
    main()
