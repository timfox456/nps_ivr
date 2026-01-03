# Lead Tracking & Reconciliation

This document describes the lead tracking system for both successful and failed lead submissions to the NPA API.

## Overview

The system now tracks all lead submissions in two separate tables:
- **succeeded_leads**: Successfully submitted leads (for reconciliation)
- **failed_leads**: Failed submissions (for retry and recovery)

## Database Schema

### succeeded_leads
Stores all successfully submitted leads with complete lead data and NPA API response.

**Columns:**
- `id` (INTEGER, PRIMARY KEY)
- `lead_data` (JSON) - Complete lead information submitted
- `channel` (VARCHAR) - 'sms' or 'voice'
- `session_id` (INTEGER) - Link to conversation_sessions.id
- `submitted_at` (DATETIME, INDEXED) - When submitted to NPA API
- `npa_response` (JSON, NULLABLE) - Response from NPA API if available

**Purpose:**
- Audit trail of all successful submissions
- Reconciliation with downstream NPA API
- Data recovery if NPA system loses data
- Analytics on submission patterns

### failed_leads
Stores all failed lead submissions for manual retry.

**Columns:**
- `id` (INTEGER, PRIMARY KEY)
- `lead_data` (JSON) - Complete lead information
- `error_message` (TEXT) - Error details for debugging
- `channel` (VARCHAR) - 'sms' or 'voice'
- `session_id` (INTEGER) - Link to conversation_sessions.id
- `retry_count` (INTEGER) - Number of retry attempts
- `last_retry_at` (DATETIME) - Timestamp of last retry
- `created_at` (DATETIME) - When lead submission first failed
- `resolved` (BOOLEAN) - 0=pending, 1=successfully submitted

## Automatic Tracking

### When Leads Succeed
**Location:** `app/main.py:219-231` (SMS), `app/main.py:701-713` (Voice)

When a lead is successfully submitted:
1. NPA API call succeeds
2. Lead data saved to `succeeded_leads` table
3. NPA API response (if any) saved to `npa_response` field
4. Session marked as "closed"
5. User receives completion message

### When Leads Fail
**Location:** `app/main.py:233-249` (SMS), `app/main.py:715-731` (Voice)

When a lead submission fails:
1. Exception caught from `create_lead()` call
2. Error logged but doesn't crash
3. Lead data saved to `failed_leads` table with error message
4. Session marked as "closed" to prevent auto-retry
5. User still receives completion message

**Important:** Users are not aware of the failure - they always get the completion message. This prevents frustration while allowing manual retry later.

## Management Utilities

### 1. View Failed Leads
```bash
python manage_failed_leads.py list
```

Lists all unresolved failed leads showing:
- ID, Created timestamp, Channel, Session ID
- Retry count and last retry timestamp
- Error message
- Complete lead data

### 2. Retry Failed Lead
```bash
python manage_failed_leads.py retry <id>
```

Retries submission of a specific failed lead by ID. If successful:
- Lead marked as resolved
- Lead data copied to `succeeded_leads` table
- Retry count incremented

If retry fails:
- Error message appended
- Retry count incremented
- Remains unresolved for future retry

### 3. Retry All Failed Leads
```bash
python manage_failed_leads.py retry-all
```

Batch retry of all unresolved failed leads. Shows summary of successes/failures.

### 4. View Succeeded Leads
```bash
# View all succeeded leads
python view_succeeded_leads.py

# View last 24 hours
python view_succeeded_leads.py --since 24h

# View last 7 days
python view_succeeded_leads.py --since 7d

# View only SMS leads
python view_succeeded_leads.py --channel sms

# Export to CSV
python view_succeeded_leads.py --export csv
```

Lists successfully submitted leads showing:
- ID, Submitted timestamp, Channel, Session ID
- Complete lead data
- NPA API response (if captured)

CSV export includes: id, submitted_at, channel, session_id, full_name, phone, email, zip_code, vehicle_make, vehicle_model, vehicle_year

### 5. Reconcile with NPA API
```bash
# Reconcile all succeeded leads
python reconcile_leads.py

# Reconcile last 24 hours
python reconcile_leads.py --since 24h

# Reconcile only SMS leads
python reconcile_leads.py --channel sms
```

**NOTE:** Currently a placeholder showing what we have in our database. Full reconciliation would require NPA API to provide:
1. GET endpoint to query leads by phone/email
2. Lead ID in submission response for direct lookup
3. Webhook for lead status updates

## Use Cases

### Scenario 1: NPA API Credentials Expired
**Symptom:** Conversations complete but no leads show up in NPA system

**Resolution:**
1. Check logs: `journalctl -u nps-ivr --since "1 hour ago" | grep "Failed to create lead"`
2. List failed leads: `python manage_failed_leads.py list`
3. Update NPA API credentials in `.env`
4. Retry all: `python manage_failed_leads.py retry-all`

### Scenario 2: NPA API Temporarily Down
**Symptom:** Multiple failed submissions during outage window

**Resolution:**
1. Wait for NPA API to recover
2. List failed leads: `python manage_failed_leads.py list`
3. Retry all: `python manage_failed_leads.py retry-all`

### Scenario 3: Reconciliation After Issue
**Symptom:** Uncertainty about which leads made it through during incident

**Resolution:**
1. Export succeeded leads: `python view_succeeded_leads.py --since 24h --export csv`
2. Compare with NPA API records
3. Identify missing leads and retry: `python manage_failed_leads.py retry <id>`

### Scenario 4: Regular Audit
**Task:** Monthly verification that all leads were successfully delivered

**Process:**
1. Export month's succeeded leads: `python view_succeeded_leads.py --since 30d --export csv`
2. Request lead report from NPA API for same period
3. Compare phone numbers/emails
4. Investigate discrepancies

## SQL Queries for Reconciliation

### Count submissions by channel and date
```sql
SELECT
    DATE(submitted_at) as date,
    channel,
    COUNT(*) as count
FROM succeeded_leads
GROUP BY DATE(submitted_at), channel
ORDER BY date DESC;
```

### Find succeeded leads without NPA response
```sql
SELECT id, submitted_at, channel, lead_data
FROM succeeded_leads
WHERE npa_response IS NULL
ORDER BY submitted_at DESC;
```

### Compare failed vs succeeded rates
```sql
SELECT
    'succeeded' as status,
    channel,
    COUNT(*) as count
FROM succeeded_leads
WHERE submitted_at >= datetime('now', '-7 days')
GROUP BY channel

UNION ALL

SELECT
    'failed' as status,
    channel,
    COUNT(*) as count
FROM failed_leads
WHERE created_at >= datetime('now', '-7 days')
    AND resolved = 0
GROUP BY channel;
```

### Find leads by phone number
```sql
SELECT
    id,
    submitted_at,
    channel,
    json_extract(lead_data, '$.phone') as phone,
    json_extract(lead_data, '$.email') as email,
    json_extract(lead_data, '$.full_name') as name
FROM succeeded_leads
WHERE json_extract(lead_data, '$.phone') = '+15551234567'
ORDER BY submitted_at DESC;
```

## Future Enhancements

### 1. NPA API Integration
- Add `npa_lead_id` field to `succeeded_leads` table
- Capture lead ID from NPA API response
- Enable direct lookup for reconciliation

### 2. Automated Reconciliation
- Scheduled job to compare our records with NPA API
- Alert on discrepancies
- Auto-retry missing leads

### 3. Webhooks
- NPA API sends webhook when lead status changes
- Update our records automatically
- Track lead lifecycle (submitted → contacted → sold)

### 4. Dashboard
- Web UI for viewing failed/succeeded leads
- One-click retry
- Reconciliation report
- Success rate metrics

### 5. Alerting
- Email/SMS when failed lead count exceeds threshold
- Alert when success rate drops below X%
- Daily summary of submissions

## Troubleshooting

### No succeeded leads showing up
```bash
# Check if table exists
python3 -c "from app.db import engine; from sqlalchemy import inspect; print(inspect(engine).get_table_names())"

# Check if any rows exist
python3 -c "from app.db import SessionLocal; from app.models import SucceededLead; db = SessionLocal(); print(f'Count: {db.query(SucceededLead).count()}'); db.close()"
```

### Failed leads not being saved
```bash
# Check logs for errors
journalctl -u nps-ivr --since "1 hour ago" | grep -i "failed\|error"

# Verify table schema
python3 -c "from app.db import engine; from sqlalchemy import inspect; print([col['name'] for col in inspect(engine).get_columns('failed_leads')])"
```

### Retry not working
```bash
# Run retry with verbose output
python manage_failed_leads.py retry <id>

# Check if NPA API credentials are valid
# Update .env if expired
```

## Best Practices

1. **Regular Monitoring**: Run `python manage_failed_leads.py list` daily to check for failures
2. **Monthly Reconciliation**: Export succeeded leads monthly and compare with NPA records
3. **Quick Recovery**: Keep NPA API credentials up to date to enable immediate retry
4. **Data Retention**: Keep succeeded_leads for at least 90 days for audit purposes
5. **Backup**: Regularly backup `nps_ivr.db` to preserve lead history

## Related Files

- `app/models.py:24-48` - FailedLead and SucceededLead model definitions
- `app/main.py:215-249` - SMS lead submission with tracking
- `app/main.py:696-733` - Voice lead submission with tracking
- `manage_failed_leads.py` - Failed lead management utility
- `view_succeeded_leads.py` - Succeeded lead viewer with export
- `reconcile_leads.py` - Reconciliation utility (placeholder)

---

**Last Updated:** 2025-01-16
**Version:** 1.0
