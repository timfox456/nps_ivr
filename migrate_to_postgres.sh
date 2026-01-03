#!/bin/bash
set -e

echo "========================================"
echo "NPS IVR: SQLite to PostgreSQL Migration"
echo "========================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Step 1: Install PostgreSQL
echo -e "${YELLOW}Step 1: Installing PostgreSQL...${NC}"
sudo apt-get update
sudo apt-get install -y postgresql postgresql-contrib libpq-dev

# Step 2: Start PostgreSQL service
echo -e "${YELLOW}Step 2: Starting PostgreSQL service...${NC}"
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Step 3: Create database and user
echo -e "${YELLOW}Step 3: Creating database and user...${NC}"
sudo -u postgres psql <<EOF
-- Create database
CREATE DATABASE nps_ivr;

-- Create user
CREATE USER nps_ivr_user WITH PASSWORD 'nps_ivr_password_change_me';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE nps_ivr TO nps_ivr_user;

-- Connect to the database and grant schema privileges (PostgreSQL 15+)
\c nps_ivr
GRANT ALL ON SCHEMA public TO nps_ivr_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO nps_ivr_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO nps_ivr_user;

\q
EOF

echo -e "${GREEN}✓ PostgreSQL installed and configured${NC}"
echo ""

# Step 4: Install Python PostgreSQL driver
echo -e "${YELLOW}Step 4: Installing psycopg2 (PostgreSQL driver)...${NC}"
cd /home/tfox/timfox456/nps_ivr
source .venv/bin/activate
pip install psycopg2-binary

echo -e "${GREEN}✓ psycopg2 installed${NC}"
echo ""

# Step 5: Update requirements.txt
echo -e "${YELLOW}Step 5: Updating requirements.txt...${NC}"
if ! grep -q "psycopg2-binary" requirements.txt; then
    echo "psycopg2-binary>=2.9.9" >> requirements.txt
    echo -e "${GREEN}✓ Added psycopg2-binary to requirements.txt${NC}"
else
    echo -e "${GREEN}✓ psycopg2-binary already in requirements.txt${NC}"
fi
echo ""

# Step 6: Backup existing SQLite database
echo -e "${YELLOW}Step 6: Backing up SQLite database...${NC}"
if [ -f "nps_ivr.db" ]; then
    cp nps_ivr.db "nps_ivr.db.backup.$(date +%Y%m%d_%H%M%S)"
    echo -e "${GREEN}✓ SQLite database backed up${NC}"
else
    echo -e "${YELLOW}⚠ No existing SQLite database found${NC}"
fi
echo ""

echo "========================================"
echo -e "${GREEN}PostgreSQL setup complete!${NC}"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Update your .env file with the PostgreSQL connection string"
echo "2. Run the data migration script: python migrate_data.py"
echo "3. Test the application with PostgreSQL"
echo "4. Restart the service: sudo systemctl restart nps-ivr"
echo ""
echo "PostgreSQL connection string:"
echo "DATABASE_URL=postgresql://nps_ivr_user:nps_ivr_password_change_me@localhost:5432/nps_ivr"
echo ""
