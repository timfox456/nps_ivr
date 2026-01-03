# PostgreSQL Setup Guide for NPS IVR

This guide will help you set up PostgreSQL alongside the existing SQLite database.

## Overview

- **SQLite**: Remains the active database (no data loss)
- **PostgreSQL**: Being added for migration/testing
- **Dual Support**: Application can switch between databases with a config flag

## Step 1: Install PostgreSQL

Run these commands with sudo access:

```bash
# Update package list
sudo apt-get update

# Install PostgreSQL and required packages
sudo apt-get install -y postgresql postgresql-contrib libpq-dev

# Verify installation
sudo systemctl status postgresql
```

## Step 2: Create Database and User

Create the database and user for the application:

```bash
sudo -u postgres psql << 'EOF'
-- Create database
CREATE DATABASE nps_ivr;

-- Create user with secure password
CREATE USER nps_ivr_user WITH PASSWORD 'CHANGE_THIS_PASSWORD';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE nps_ivr TO nps_ivr_user;

-- Connect to the database
\c nps_ivr

-- Grant schema privileges
GRANT ALL ON SCHEMA public TO nps_ivr_user;

-- Grant default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO nps_ivr_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO nps_ivr_user;

-- Show databases to verify
\l
EOF
```

**IMPORTANT**: Replace `CHANGE_THIS_PASSWORD` with a strong password!

## Step 3: Update Environment Variables

Add these lines to your `.env` file:

```bash
# PostgreSQL Configuration (for migration/testing)
POSTGRES_URL=postgresql://nps_ivr_user:YOUR_PASSWORD_HERE@localhost/nps_ivr
USE_POSTGRES=false
```

Replace `YOUR_PASSWORD_HERE` with the password you set in Step 2.

**Note**: Keep `USE_POSTGRES=false` to continue using SQLite.

## Step 4: Install Python PostgreSQL Driver

```bash
cd /home/tfox/timfox456/nps_ivr
source .venv/bin/activate
pip install psycopg2-binary==2.9.9
```

Or using uv:

```bash
cd /home/tfox/timfox456/nps_ivr
uv pip install psycopg2-binary==2.9.9
```

## Step 5: Initialize PostgreSQL Schema

Once PostgreSQL is configured, run this to create the schema:

```bash
cd /home/tfox/timfox456/nps_ivr
python3 -c "from app.db import init_db; from app.config import settings; settings.use_postgres = True; init_db(); print('PostgreSQL schema created successfully')"
```

## Step 6: Test Connection (Optional)

Test that the application can connect to PostgreSQL:

```bash
cd /home/tfox/timfox456/nps_ivr
python3 << 'EOF'
from app.config import settings
settings.use_postgres = True
settings.postgres_url = "postgresql://nps_ivr_user:YOUR_PASSWORD@localhost/nps_ivr"

from sqlalchemy import create_engine
engine = create_engine(settings.postgres_url)
conn = engine.connect()
print("✓ PostgreSQL connection successful!")
conn.close()
EOF
```

## Step 7: Data Migration (When Ready)

When you're ready to migrate data from SQLite to PostgreSQL:

```bash
cd /home/tfox/timfox456/nps_ivr

# Export from SQLite
sqlite3 nps_ivr.db .dump > sqlite_dump.sql

# Import to PostgreSQL (will need conversion)
# This requires manual review as SQLite and PostgreSQL SQL dialects differ
```

Or use a Python script (recommended):

```python
# migrate_data.py
from app.db import SessionLocal as SQLiteSession
from app.models import ConversationSession
from app.config import settings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Read from SQLite
sqlite_session = SQLiteSession()
sessions = sqlite_session.query(ConversationSession).all()

# Write to PostgreSQL
settings.use_postgres = True
pg_engine = create_engine(settings.postgres_url)
PGSession = sessionmaker(bind=pg_engine)
pg_session = PGSession()

for session in sessions:
    # Create new instance to avoid session conflicts
    new_session = ConversationSession(
        channel=session.channel,
        session_key=session.session_key,
        from_number=session.from_number,
        to_number=session.to_number,
        state=session.state,
        status=session.status,
        created_at=session.created_at,
        updated_at=session.updated_at
    )
    pg_session.add(new_session)

pg_session.commit()
print(f"Migrated {len(sessions)} sessions to PostgreSQL")
```

## Step 8: Switch to PostgreSQL (When Ready)

When you're confident PostgreSQL is working correctly:

1. Update `.env`:
   ```bash
   USE_POSTGRES=true
   ```

2. Restart the application:
   ```bash
   sudo systemctl restart nps-ivr
   ```

3. Verify logs:
   ```bash
   journalctl -u nps-ivr -f | grep "Using database"
   ```

   You should see: `Using database: PostgreSQL`

## Rollback to SQLite

If you need to rollback to SQLite:

1. Update `.env`:
   ```bash
   USE_POSTGRES=false
   ```

2. Restart the application:
   ```bash
   sudo systemctl restart nps-ivr
   ```

## Database Status Check

To check which database is currently active:

```bash
# Check environment
grep USE_POSTGRES /home/tfox/timfox456/nps_ivr/.env

# Check application logs
journalctl -u nps-ivr -n 50 | grep "Using database"

# Test SQLite
sqlite3 /home/tfox/timfox456/nps_ivr/nps_ivr.db "SELECT COUNT(*) FROM conversation_sessions;"

# Test PostgreSQL
sudo -u postgres psql -d nps_ivr -c "SELECT COUNT(*) FROM conversation_sessions;"
```

## Troubleshooting

### Connection Refused

```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Check PostgreSQL is listening
sudo netstat -tlnp | grep 5432

# Check pg_hba.conf allows local connections
sudo cat /etc/postgresql/*/main/pg_hba.conf | grep local
```

### Permission Denied

```bash
# Reconnect and grant permissions again
sudo -u postgres psql -d nps_ivr -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO nps_ivr_user;"
```

### Cannot Import psycopg2

```bash
# Install system dependencies
sudo apt-get install -y libpq-dev python3-dev

# Reinstall psycopg2
cd /home/tfox/timfox456/nps_ivr
source .venv/bin/activate
pip install --force-reinstall psycopg2-binary
```

## Backup Strategy

### SQLite Backup
```bash
cp /home/tfox/timfox456/nps_ivr/nps_ivr.db /home/tfox/timfox456/nps_ivr/nps_ivr.db.backup
```

### PostgreSQL Backup
```bash
sudo -u postgres pg_dump nps_ivr > nps_ivr_backup.sql
```

## Next Steps

1. ✅ Install PostgreSQL (Step 1)
2. ✅ Create database and user (Step 2)
3. ✅ Update .env file (Step 3)
4. ✅ Install psycopg2 (Step 4)
5. Test PostgreSQL connection (Step 5)
6. Initialize PostgreSQL schema (Step 6)
7. When ready: Migrate data (Step 7)
8. When confident: Switch to PostgreSQL (Step 8)
