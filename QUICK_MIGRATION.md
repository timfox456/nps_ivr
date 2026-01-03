# Quick PostgreSQL Migration - TL;DR

## Ubuntu VM (5 minutes)

```bash
# 1. Run installation script
cd /home/tfox/timfox456/nps_ivr
./migrate_to_postgres.sh

# 2. Update .env
nano .env
# Add: DATABASE_URL=postgresql://nps_ivr_user:nps_ivr_password_change_me@localhost:5432/nps_ivr

# 3. Migrate data
source .venv/bin/activate
python migrate_data.py

# 4. Restart service
sudo systemctl restart nps-ivr

# 5. Check it works
journalctl -u nps-ivr -f
```

## Mac (5 minutes)

```bash
# 1. Install PostgreSQL
brew install postgresql@16
brew services start postgresql@16

# 2. Create database
createdb nps_ivr
psql nps_ivr -c "CREATE USER nps_ivr_user WITH PASSWORD 'dev_password';"
psql nps_ivr -c "GRANT ALL PRIVILEGES ON DATABASE nps_ivr TO nps_ivr_user;"
psql nps_ivr -c "GRANT ALL ON SCHEMA public TO nps_ivr_user;"

# 3. Install driver
cd ~/path/to/nps_ivr
source .venv/bin/activate
pip install psycopg2-binary

# 4. Update .env
# Add: DATABASE_URL=postgresql://nps_ivr_user:dev_password@localhost:5432/nps_ivr

# 5. Migrate data
python migrate_data.py

# 6. Test
uv run uvicorn app.main:app --reload
```

Done! 🎉

See POSTGRES_MIGRATION.md for detailed instructions and troubleshooting.
