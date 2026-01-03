#!/usr/bin/env python3
"""
Migrate data from SQLite to PostgreSQL
"""
import os
import sys
from sqlalchemy import create_engine, MetaData, Table
from sqlalchemy.orm import sessionmaker

# SQLite connection
SQLITE_URL = "sqlite:///./nps_ivr.db"

# PostgreSQL connection (update with your actual password)
POSTGRES_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://nps_ivr_user:nps_ivr_password_change_me@localhost:5432/nps_ivr"
)

def migrate():
    print("=" * 60)
    print("Starting data migration from SQLite to PostgreSQL")
    print("=" * 60)
    print()

    # Check if SQLite database exists
    if not os.path.exists("nps_ivr.db"):
        print("⚠️  No SQLite database found at ./nps_ivr.db")
        print("   Creating fresh PostgreSQL schema instead...")
        create_fresh_schema()
        return

    try:
        # Create engines
        print("Connecting to SQLite...")
        sqlite_engine = create_engine(SQLITE_URL)

        print("Connecting to PostgreSQL...")
        postgres_engine = create_engine(POSTGRES_URL)

        # Create sessions
        SqliteSession = sessionmaker(bind=sqlite_engine)
        PostgresSession = sessionmaker(bind=postgres_engine)

        sqlite_session = SqliteSession()
        postgres_session = PostgresSession()

        # Get metadata from SQLite
        print("Reading SQLite schema...")
        sqlite_metadata = MetaData()
        sqlite_metadata.reflect(bind=sqlite_engine)

        # Create tables in PostgreSQL
        print("Creating tables in PostgreSQL...")
        postgres_metadata = MetaData()

        # Import models to create schema
        from app.models import Base
        Base.metadata.create_all(bind=postgres_engine)

        print("✓ PostgreSQL schema created")
        print()

        # Migrate data table by table
        for table_name in sqlite_metadata.tables.keys():
            print(f"Migrating table: {table_name}")

            sqlite_table = Table(table_name, sqlite_metadata, autoload_with=sqlite_engine)
            postgres_table = Table(table_name, postgres_metadata, autoload_with=postgres_engine)

            # Read all data from SQLite
            rows = sqlite_session.execute(sqlite_table.select()).fetchall()

            if rows:
                # Convert to dictionaries
                data_dicts = [dict(row._mapping) for row in rows]

                # Insert into PostgreSQL
                postgres_session.execute(postgres_table.insert(), data_dicts)
                postgres_session.commit()

                print(f"  ✓ Migrated {len(rows)} rows")
            else:
                print(f"  ⚠ No data to migrate")

            print()

        sqlite_session.close()
        postgres_session.close()

        print("=" * 60)
        print("✓ Migration completed successfully!")
        print("=" * 60)
        print()
        print("Next steps:")
        print("1. Update .env file with PostgreSQL connection string")
        print("2. Test the application")
        print("3. Restart the service: sudo systemctl restart nps-ivr")
        print()

    except Exception as e:
        print(f"❌ Error during migration: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


def create_fresh_schema():
    """Create fresh PostgreSQL schema without migrating data"""
    try:
        print("Creating fresh PostgreSQL schema...")
        postgres_engine = create_engine(POSTGRES_URL)

        from app.models import Base
        Base.metadata.create_all(bind=postgres_engine)

        print("✓ PostgreSQL schema created")
        print()
        print("Database is ready to use!")
        print()

    except Exception as e:
        print(f"❌ Error creating schema: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    # Check if we should use a custom PostgreSQL URL
    if len(sys.argv) > 1:
        POSTGRES_URL = sys.argv[1]
        print(f"Using custom PostgreSQL URL: {POSTGRES_URL}")
        print()

    migrate()
