# Docker Deployment Guide - NPS IVR

This guide explains how to deploy the NPS IVR system using Docker in a single mono-container with SQLite.

## Architecture

- **Container**: Single mono-container running FastAPI with Uvicorn
- **Database**: SQLite (persistent via volume mount)
- **Logging**: JSON logs to STDOUT (12-factor app)
- **Port**: 8000 (HTTP)

## Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- `.env` file with credentials (see `.env.example`)

## Quick Start

### 1. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your actual credentials
nano .env
```

### 2. Build and Run

```bash
# Build and start the container
docker-compose up -d

# View logs
docker-compose logs -f

# Check container status
docker-compose ps
```

### 3. Verify Deployment

```bash
# Check health endpoint
curl http://localhost:8000/health

# Should return: {"status":"ok"}
```

### 4. Configure Twilio Webhooks

Point your Twilio webhooks to your server:

- **SMS Webhook**: `POST http://YOUR_SERVER:8000/twilio/sms`
- **Voice Webhook**: `POST http://YOUR_SERVER:8000/twilio/voice`

If using ngrok for testing:
```bash
ngrok http 8000
# Then update webhooks to use the ngrok URL
```

## Management Commands

### View Logs

```bash
# Follow logs in real-time
docker-compose logs -f nps-ivr

# View last 100 lines
docker-compose logs --tail=100 nps-ivr

# Filter for errors
docker-compose logs nps-ivr | grep ERROR
```

### Restart Container

```bash
docker-compose restart nps-ivr
```

### Stop and Start

```bash
# Stop container (data persists)
docker-compose stop

# Start container
docker-compose start

# Stop and remove container (data persists in volume)
docker-compose down

# Stop and remove container + volumes (WARNING: deletes database!)
docker-compose down -v
```

### Rebuild After Code Changes

```bash
# Rebuild and restart
docker-compose up -d --build

# Or force rebuild
docker-compose build --no-cache
docker-compose up -d
```

## Data Persistence

The SQLite database is stored in `./data/nps_ivr.db` and persists across container restarts.

### Backup Database

```bash
# Backup
cp ./data/nps_ivr.db ./data/nps_ivr.db.backup.$(date +%Y%m%d_%H%M%S)

# Restore
cp ./data/nps_ivr.db.backup.YYYYMMDD_HHMMSS ./data/nps_ivr.db
docker-compose restart nps-ivr
```

### View Database

```bash
# Access SQLite database
sqlite3 ./data/nps_ivr.db

# Or use Docker
docker-compose exec nps-ivr sqlite3 /data/nps_ivr.db
```

## Monitoring

### Health Checks

The container includes automatic health checks:

```bash
# Check health status
docker inspect --format='{{.State.Health.Status}}' nps-ivr

# View health check logs
docker inspect nps-ivr | jq '.[0].State.Health'
```

### Resource Usage

```bash
# View resource usage
docker stats nps-ivr

# View container details
docker inspect nps-ivr
```

### Log Analysis

Since logs are in JSON format, you can use `jq` for filtering:

```bash
# Show only errors
docker-compose logs nps-ivr | grep '"level":"ERROR"' | jq

# Show API calls
docker-compose logs nps-ivr | grep 'NPA API' | jq

# Show successful leads
docker-compose logs nps-ivr | grep 'Successfully created' | jq
```

## Production Deployment

### Reverse Proxy (Nginx/Caddy)

For production, place the container behind a reverse proxy:

**Nginx Example:**
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### HTTPS/SSL

Use Caddy (automatic HTTPS) or Certbot with Nginx:

```bash
# Using Caddy (easiest)
caddy reverse-proxy --from your-domain.com --to localhost:8000
```

### Resource Limits

Adjust in `docker-compose.yml`:

```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'        # Increase for more throughput
      memory: 1G         # Increase if needed
```

### Auto-Restart

The container is configured with `restart: unless-stopped`, so it will automatically restart if it crashes or after server reboot.

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs nps-ivr

# Check if port is in use
sudo lsof -i :8000

# Rebuild
docker-compose down
docker-compose up -d --build
```

### Database Locked

```bash
# Stop container
docker-compose stop

# Remove lock files
rm -f ./data/nps_ivr.db-shm ./data/nps_ivr.db-wal

# Restart
docker-compose start
```

### Environment Variables Not Loading

```bash
# Verify .env file exists
cat .env

# Check loaded environment
docker-compose exec nps-ivr env | grep TWILIO
```

### Twilio Webhooks Not Working

1. Check firewall allows port 8000
2. Verify webhooks point to correct URL
3. Check logs for incoming requests
4. Test locally with ngrok first

## Updating

```bash
# Pull latest code
git pull

# Rebuild and restart
docker-compose up -d --build

# Verify
docker-compose logs -f nps-ivr
```

## Migration from VM

If migrating from the current VM setup:

```bash
# 1. Stop VM service
sudo systemctl stop nps-ivr

# 2. Copy database
cp /path/to/nps_ivr.db ./data/

# 3. Start Docker container
docker-compose up -d

# 4. Verify
docker-compose logs -f
curl http://localhost:8000/health
```

## Log Aggregation (Optional)

For centralized logging, configure Docker logging driver:

```yaml
# In docker-compose.yml
logging:
  driver: "syslog"
  options:
    syslog-address: "tcp://your-log-server:514"
    tag: "nps-ivr"
```

Or use a log aggregator like Loki, Elasticsearch, or cloud services.

## Performance Tuning

### For High Call Volume

1. **Increase resources:**
   ```yaml
   deploy:
     resources:
       limits:
         cpus: '2.0'
         memory: 1G
   ```

2. **Add multiple workers:**
   ```dockerfile
   CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
   ```

3. **Use Redis for session caching** (future enhancement)

## Security Best Practices

1. ✅ Never commit `.env` file
2. ✅ Use Docker secrets in production
3. ✅ Run container as non-root user (future enhancement)
4. ✅ Keep base images updated
5. ✅ Use reverse proxy with HTTPS
6. ✅ Limit container resources
7. ✅ Regular database backups

## Support

For issues or questions:
- Check logs: `docker-compose logs -f`
- Review health status: `docker inspect nps-ivr`
- Test locally with ngrok before production deployment
