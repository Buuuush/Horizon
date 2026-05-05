# Docker Deployment Guide

## Overview

Horizon supports Docker deployment with two services:
- **Dashboard** - Web UI on port 5000 for browsing summaries and managing profiles
- **Orchestrator** - CLI process that runs scraping, analysis, and summarization

## Quick Start

### Run Everything (Dashboard + Orchestrator)

```bash
# Build images
docker-compose build

# Start services
docker-compose up -d

# Access dashboard
open http://localhost:5000
```

### Just Dashboard

```bash
docker-compose up -d dashboard
# Dashboard runs and waits for orchestrator tasks
# Access: http://localhost:5000
```

### Just Orchestrator (One-time Run)

```bash
# Run once and exit
docker-compose run --rm orchestrator

# Or with custom theme
docker-compose run --rm orchestrator --theme "informatique"
```

## Configuration

### Environment Setup

```bash
# Copy and edit environment
cp .env.example .env

# Required: Set at least one API key
export OPENAI_API_KEY="sk-..."
# or
export ANTHROPIC_API_KEY="sk-ant-..."
# or
export GOOGLE_API_KEY="..."
```

### Config File

```bash
# Copy and customize config
cp data/config.example.json data/config.json

# Edit to add your sources
nano data/config.json
```

### data/ Volume

The `data/` directory is mounted to both services:
- `config.json` - Configuration (shared)
- `profiles.json` - Profile definitions (shared)
- `summaries/` - Generated HTML/MD summaries (shared)
- `feedback.db` - SQLite database (shared)
- `horizon.db` - Profile/cache database (shared)

## Services

### Dashboard Service

**Container**: `horizon-dashboard`  
**Port**: 5000  
**Command**: `python -m uvicorn src.web.app:app --host 0.0.0.0 --port 5000`  
**Restart**: Unless stopped  
**Health Check**: Queries `/health` endpoint every 30s

**Features**:
- Browse and rate articles
- Manage profiles
- View accuracy stats
- Real-time progress via WebSocket

**Usage**:
```bash
# Start dashboard
docker-compose up -d dashboard

# View logs
docker-compose logs -f dashboard

# Stop dashboard
docker-compose stop dashboard
```

### Orchestrator Service

**Container**: `horizon-orchestrator`  
**Depends On**: `horizon-dashboard` (waits for health check)  
**Command**: `--hours 24 --summary-format html`  
**Restart**: Unless stopped  
**Restart Policy**: Waits for dashboard to be healthy

**Features**:
- Scrapes all configured sources
- Analyzes with AI
- Generates bilingual summaries
- Broadcasts progress to dashboard

**Usage**:
```bash
# One-time run
docker-compose run --rm orchestrator

# Run with custom theme
docker-compose run --rm orchestrator --theme "ML papers"

# Run with different time window
docker-compose run --rm orchestrator --hours 48

# Run with markdown format
docker-compose run --rm orchestrator --summary-format md

# View logs
docker-compose logs -f orchestrator
```

## Production Deployment

### Scheduling Regular Runs

#### Option 1: Docker Compose + Cron

```bash
# Edit crontab
crontab -e

# Add daily run at 8:00 AM UTC
0 8 * * * cd /path/to/horizon && docker-compose run --rm orchestrator

# Add daily run with theme
0 8 * * * cd /path/to/horizon && docker-compose run --rm orchestrator --theme "informatique"
```

#### Option 2: Docker Container with cron

Build a custom image with cron:

```dockerfile
FROM python:3.11-slim

# ... (copy Horizon files) ...

# Install cron
RUN apt-get update && apt-get install -y cron && rm -rf /var/lib/apt/lists/*

# Copy crontab
COPY crontab /etc/cron.d/horizon

# Give execution rights
RUN chmod 0644 /etc/cron.d/horizon

# Start cron in foreground
CMD ["cron", "-f"]
```

#### Option 3: Kubernetes CronJob

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: horizon-daily
spec:
  schedule: "0 8 * * *"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: horizon
            image: horizon:latest
            command: ["uv", "run", "horizon", "--hours", "24"]
            volumeMounts:
            - name: data
              mountPath: /app/data
          restartPolicy: OnFailure
          volumes:
          - name: data
            persistentVolumeClaim:
              claimName: horizon-data
```

### Resource Limits

Current settings in docker-compose.yml:

```yaml
dashboard:
  limits:
    cpus: '4'
    memory: 4G
  reservations:
    cpus: '2'
    memory: 2G

orchestrator:
  limits:
    cpus: '16'
    memory: 16G
  reservations:
    cpus: '12'
    memory: 10G
```

Adjust based on your system:
- More RSS sources → more memory
- More concurrent AI calls → more CPU
- Typical: 2GB sufficient for 50 sources

### Persistent Storage

```bash
# Create volume for data
docker volume create horizon-data

# Update docker-compose.yml
volumes:
  data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /path/to/data
```

## Networking

### Local Development

```bash
# Both services on localhost
# Dashboard: http://localhost:5000
# Orchestrator: connects internally via container network
```

### Remote Deployment

```bash
# Allow external access to dashboard
# (from docker-compose.yml)
ports:
  - "0.0.0.0:5000:5000"  # Listen on all interfaces

# Or use reverse proxy (nginx, Caddy)
# https://your-domain.com/dashboard -> localhost:5000
```

### Container Network

Services communicate via Docker network:

```
orchestrator → dashboard (via http://dashboard:5000)
browser → dashboard (via http://localhost:5000)
```

## Troubleshooting

### Dashboard won't start

```bash
# Check logs
docker-compose logs dashboard

# Verify port 5000 is available
lsof -i :5000

# Rebuild image
docker-compose build --no-cache dashboard
```

### Orchestrator fails to connect

```bash
# Check dashboard health
docker-compose exec dashboard curl http://localhost:5000/health

# Verify data volume mount
docker-compose exec orchestrator ls /app/data

# Check for config file
docker-compose exec orchestrator ls -la /app/data/config.json
```

### WebSocket not connecting

```bash
# Check WebSocket endpoint
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" \
  http://localhost:5000/ws/progress/default

# Check browser console for errors
# Look for "Failed to connect WebSocket"
```

### Out of memory

```bash
# Increase memory limits
# Edit docker-compose.yml:
limits:
  memory: 32G

# Or run with less data
docker-compose run --rm orchestrator --hours 12
```

## Maintenance

### Backup

```bash
# Backup data volume
docker run --rm -v horizon-data:/data -v $(pwd):/backup \
  alpine tar czf /backup/horizon-data.tar.gz /data
```

### Restore

```bash
# Restore data volume
docker run --rm -v horizon-data:/data -v $(pwd):/backup \
  alpine tar xzf /backup/horizon-data.tar.gz -C /
```

### Logs

```bash
# View all logs
docker-compose logs

# Follow logs
docker-compose logs -f

# Dashboard only
docker-compose logs dashboard

# Last 100 lines
docker-compose logs --tail=100
```

### Clean Up

```bash
# Stop all services
docker-compose stop

# Remove containers (keep images)
docker-compose rm

# Remove everything (including images)
docker-compose down -v

# Remove dangling images
docker image prune -a
```

## Advanced Configuration

### Multi-Profile Runs

```bash
# Run with different profile
docker-compose run --rm orchestrator --profile ml-research

# Schedule multiple runs
0 8 * * * docker-compose run --rm orchestrator --profile ml-research
0 8 * * * docker-compose run --rm orchestrator --profile news
```

### Custom Entry Point

```bash
# Run custom command
docker-compose run --rm orchestrator --manage-profiles

# Show feedback stats
docker-compose run --rm orchestrator --show-feedback-stats ml-research

# Clear cache
docker-compose run --rm orchestrator --clear-cache
```

### Environment Variables

```bash
# In .env file
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...
HORIZON_LOG_LEVEL=INFO
```

## Monitoring

### Health Checks

```bash
# Check dashboard health
curl http://localhost:5000/health

# Check if running
docker-compose ps

# Check resource usage
docker stats horizon-dashboard horizon-orchestrator
```

### Metrics

```bash
# View container logs with timestamps
docker-compose logs --timestamps

# Export metrics (Prometheus-compatible)
# Set up monitoring stack with docker-compose

# See Phase 5 for full monitoring setup
```

---

## Examples

### Example 1: Daily Run

```bash
# Start all services
docker-compose up -d

# Orchestrator will run daily at 8 AM UTC
# Results visible on http://localhost:5000

# To trigger manually
docker-compose run --rm orchestrator
```

### Example 2: Multi-Source Setup

```yaml
# docker-compose.override.yml
services:
  orchestrator:
    environment:
      - HORIZON_THEME=Technology
    command: ["--hours", "48", "--theme", "Tech News"]
```

### Example 3: High-Volume Scraping

```yaml
# For many sources, increase limits
orchestrator:
  deploy:
    resources:
      limits:
        cpus: '24'
        memory: 32G
```

## Next Steps

- **Phase 5**: Monitoring and logging setup
- **Phase 6**: Multi-region deployment
- **Phase 7**: Load balancing and failover

---

**Status**: ✅ Phase 4B Docker Updates Complete  
**Documentation**: Complete with examples and troubleshooting  
**Date**: May 5, 2026
