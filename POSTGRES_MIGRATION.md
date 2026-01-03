# PostgreSQL Migration Guide

This guide will help you migrate from SQLite to PostgreSQL on both your Ubuntu VM and Mac development machine.

## Why Migrate to PostgreSQL?

- **Better concurrency**: Handle multiple simultaneous calls
- **Production-ready**: Industry standard for web applications
- **Scalability**: Supports connection pooling, replication
- **Azure compatibility**: Easy path to Azure Database for PostgreSQL

---

## Migration Steps

### Ubuntu VM (Production)

#### 1. Run the installation script

```bash
cd /home/tfox/timfox456/nps_ivr
chmod +x migrate_to_postgres.sh
./migrate_to_postgres.sh
```

This will:
- Install PostgreSQL 16
- Create database `nps_ivr`
- Create user `nps_ivr_user`
- Install Python driver `psycopg2-binary`
- Backup your SQLite database

#### 2. Update your `.env` file

```bash
# Edit .env
nano .env
```

Add or update the `DATABASE_URL` line:

```bash
DATABASE_URL=postgresql://nps_ivr_user:nps_ivr_password_change_me@localhost:5432/nps_ivr
```

**IMPORTANT**: Change the password! Update both the `.env` file AND PostgreSQL:

```bash
sudo -u postgres psql
```

```sql
ALTER USER nps_ivr_user WITH PASSWORD 'your_secure_password_here';
\q
```

Then update `.env` with the new password.

#### 3. Migrate your data

```bash
source .venv/bin/activate
python migrate_data.py
```

This will:
- Create tables in PostgreSQL
- Copy all data from SQLite
- Report number of rows migrated

#### 4. Test the connection

```bash
# Test PostgreSQL connection
python -c "
from app.db import SessionLocal
db = SessionLocal()
print('✓ PostgreSQL connection successful!')
db.close()
"
```

#### 5. Restart the service

```bash
sudo systemctl restart nps-ivr
sudo systemctl status nps-ivr
```

#### 6. Verify it's working

```bash
# Check logs
journalctl -u nps-ivr -f --no-pager
```

Make a test call or send a test SMS to verify everything works.

#### 7. (Optional) Keep SQLite backup

Your SQLite database is backed up at `nps_ivr.db.backup.<timestamp>`. Keep it for a week or two, then delete it once you're confident PostgreSQL is working:

```bash
# After a week or two, if everything is working:
rm nps_ivr.db.backup.*
rm nps_ivr.db  # Remove original SQLite file
```

---

### Mac Development Machine

#### 1. Install PostgreSQL using Homebrew

```bash
# Install PostgreSQL
brew install postgresql@16

# Start PostgreSQL
brew services start postgresql@16

# Add to PATH (add to ~/.zshrc or ~/.bash_profile)
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"
```

#### 2. Create database and user

```bash
# Create database
createdb nps_ivr

# Set up user and permissions
psql nps_ivr
```

```sql
CREATE USER nps_ivr_user WITH PASSWORD 'nps_ivr_dev_password';
GRANT ALL PRIVILEGES ON DATABASE nps_ivr TO nps_ivr_user;
GRANT ALL ON SCHEMA public TO nps_ivr_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO nps_ivr_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO nps_ivr_user;
\q
```

#### 3. Install Python PostgreSQL driver

```bash
cd ~/path/to/nps_ivr
source .venv/bin/activate  # or your venv activation command
pip install psycopg2-binary
```

#### 4. Update your `.env` file

```bash
# Edit .env
nano .env
```

```bash
DATABASE_URL=postgresql://nps_ivr_user:nps_ivr_dev_password@localhost:5432/nps_ivr
```

#### 5. Migrate data (if you have existing data)

```bash
python migrate_data.py
```

#### 6. Test locally

```bash
uv run uvicorn app.main:app --reload --port 8000
```

Test with a call or SMS to make sure everything works.

---

## Troubleshooting

### Connection refused

**Error**: `connection refused` or `could not connect to server`

**Solution**:
```bash
# Check if PostgreSQL is running
sudo systemctl status postgresql

# Start it if needed
sudo systemctl start postgresql
```

### Authentication failed

**Error**: `password authentication failed for user "nps_ivr_user"`

**Solution**: Reset the password
```bash
sudo -u postgres psql
ALTER USER nps_ivr_user WITH PASSWORD 'new_password';
\q
```

Update `.env` with the new password.

### Permission denied on schema public

**Error**: `permission denied for schema public`

**Solution**: Grant schema permissions
```bash
sudo -u postgres psql -d nps_ivr
```

```sql
GRANT ALL ON SCHEMA public TO nps_ivr_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO nps_ivr_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO nps_ivr_user;
\q
```

### Port already in use (Mac)

**Error**: PostgreSQL won't start because port 5432 is in use

**Solution**: Check what's using the port
```bash
lsof -i :5432
# Kill the process or change PostgreSQL port in postgresql.conf
```

---

## Verification Checklist

After migration, verify:

- [ ] Application starts without errors
- [ ] Can make voice calls successfully
- [ ] Can send/receive SMS
- [ ] Data from previous sessions is visible
- [ ] New sessions are being created
- [ ] No database errors in logs

---

## Performance Tuning (Optional)

For production use, tune PostgreSQL settings:

```bash
sudo nano /etc/postgresql/16/main/postgresql.conf
```

Recommended changes for a small VM:
```conf
max_connections = 100
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 2621kB
min_wal_size = 1GB
max_wal_size = 4GB
```

After changes:
```bash
sudo systemctl restart postgresql
```

---

## Rollback Plan (If Something Goes Wrong)

If you need to rollback to SQLite:

1. Stop the service:
   ```bash
   sudo systemctl stop nps-ivr
   ```

2. Edit `.env` and change back to SQLite:
   ```bash
   DATABASE_URL=sqlite:///./nps_ivr.db
   ```

3. Restore from backup if needed:
   ```bash
   cp nps_ivr.db.backup.TIMESTAMP nps_ivr.db
   ```

4. Restart:
   ```bash
   sudo systemctl start nps-ivr
   ```

---

## Next Steps After Migration

Once PostgreSQL is working on both machines:

1. **Enable connection pooling** (for production)
2. **Set up automated backups**
3. **Consider migrating to Azure Database for PostgreSQL** for production
4. **Remove SQLite files** after confirming everything works

---

## Questions?

If you encounter issues:
1. Check the logs: `journalctl -u nps-ivr -f`
2. Test PostgreSQL connection: `psql -U nps_ivr_user -d nps_ivr -h localhost`
3. Verify `.env` has correct `DATABASE_URL`
