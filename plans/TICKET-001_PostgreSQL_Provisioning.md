# TICKET-001: PostgreSQL 15+ Database with Connection Pooling

## Overview
Provision PostgreSQL 15+ database with connection pooling configuration for the Agentic Spec Builder system.

## Requirements
- PostgreSQL 15+ with async driver support
- Connection pooling using PgBouncer or built-in pooling
- SSL/TLS encryption for data in transit
- Automated backups with point-in-time recovery
- Monitoring and health checks

## Implementation Plan

### 1. Docker Compose Configuration

Create `infrastructure/docker-compose.postgres.yml`:

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    container_name: specgen_postgres
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-specgen}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-secure_password}
      POSTGRES_DB: ${POSTGRES_DB:-specgen}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init-scripts:/docker-entrypoint-initdb.d
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 5
    command: |
      postgres
      -c max_connections=200
      -c shared_buffers=256MB
      -c effective_cache_size=768MB
      -c work_mem=16MB
      -c maintenance_work_mem=128MB
      -c checkpoint_completion_target=0.9
      -c wal_buffers=16MB
      -c default_statistics_target=100
      -c ssl=on
      -c ssl_cert_file=/certs/server.crt
      -c ssl_key_file=/certs/server.key

  pgbouncer:
    image: pgbouncer/pgbouncer:alpine
    container_name: specgen_pgbouncer
    environment:
      DATABASES_HOST: postgres
      DATABASES_PORT: 5432
      DATABASES_USER: ${POSTGRES_USER}
      DATABASES_PASSWORD: ${POSTGRES_PASSWORD}
      DATABASES_NAME: ${POSTGRES_DB}
      PGBOUNCER_LISTEN_PORT: 6432
      PGBOUNCER_AUTH_TYPE: md5
      PGBOUNCER_POOL_MODE: transaction
      PGBOUNCER_MAX_CLIENT_CONN: 100
      PGBOUNCER_DEFAULT_POOL_SIZE: 20
      PGBOUNCER_MIN_POOL_SIZE: 5
      PGBOUNCER_RESERVE_POOL_SIZE: 5
      PGBOUNCER_SERVER_IDLE_TIMEOUT: 600
      PGBOUNCER_LOG_CONNECTIONS: 0
      PGBOUNCER_LOG_DISCONNECTIONS: 0
      PGBOUNCER_LOG_QUERY: 0
    ports:
      - "6432:6432"
    depends_on:
      - postgres
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -h localhost -p 6432 -U ${POSTGRES_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
    driver: local
```

### 2. Environment Configuration

Create `.env.example`:

```bash
# PostgreSQL Configuration
POSTGRES_USER=specgen
POSTGRES_PASSWORD=your_secure_password_here
POSTGRES_DB=specgen

# PgBouncer Configuration
PGBOUNCER_HOST=localhost
PGBOUNCER_PORT=6432
PGBOUNCER_USER=specgen
PGBOUNCER_PASSWORD=your_pgbouncer_password_here

# Database Connection
DATABASE_URL=postgresql+asyncpg://specgen:password@localhost:6432/specgen
DATABASE_URL_SYNC=postgresql+psycopg2://specgen:password@localhost:6432/specgen

# SSL Configuration
POSTGRES_SSL_MODE=require
POSTGRES_SSL_CERT=/certs/client.crt
POSTGRES_SSL_KEY=/certs/client.key
POSTGRES_SSL_ROOT_CERT=/certs/root.crt

# Connection Pool Settings
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=1800
```

### 3. SQLAlchemy Async Configuration

Create `backend/db/connection.py`:

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://specgen:password@localhost:6432/specgen"
)

# Async engine for FastAPI
async_engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=int(os.getenv("DB_POOL_SIZE", "20")),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
    pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "30")),
    pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "1800")),
    ssl=os.getenv("POSTGRES_SSL_MODE", "require") == "require",
)

# Async session factory
async_session_factory = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()

async def init_db():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def close_db():
    await async_engine.dispose()
```

### 4. Database Initialization Script

Create `backend/db/init_schema.py`:

```python
from sqlalchemy import (
    Column, String, UUID, Integer, DateTime, Text, Boolean, 
    JSONB, ForeignKey, Numeric, ARRAY, Index, CheckConstraint
)
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
import uuid

# Users table (TICKET-015)
users = Table(
    "users",
    metadata,
    Column("id", PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("email", String(255), unique=True, nullable=False, index=True),
    Column("password_hash", String(255), nullable=False),
    Column("full_name", String(255)),
    Column("avatar_url", String(512)),
    Column("is_active", Boolean, default=True),
    Column("is_verified", Boolean, default=False),
    Column("two_factor_enabled", Boolean, default=False),
    Column("two_factor_secret", String(255)),
    Column("oauth_providers", ARRAY(String)),
    Column("last_login_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
)

# Additional tables from TICKET-016 to TICKET-029...
```

### 5. Backup Configuration

Create `infrastructure/backup-postgres.sh`:

```bash
#!/bin/bash
set -e

# Configuration
BACKUP_DIR="/backups/postgres"
RETENTION_DAYS=30
DATABASE_NAME="${POSTGRES_DB:-specgen}"
DATABASE_USER="${POSTGRES_USER:-specgen}"

# Create backup directory
mkdir -p "${BACKUP_DIR}"

# Create backup with point-in-time recovery support
BACKUP_FILE="${BACKUP_DIR}/${DATABASE_NAME}_$(date +%Y%m%d_%H%M%S).sql.gz"

echo "Starting PostgreSQL backup..."

# Perform backup with compression
pg_dump -U "${DATABASE_USER}" -h localhost -p 5432 "${DATABASE_NAME}" \
    --format=custom \
    --compress=9 \
    --verbose \
    --file="${BACKUP_FILE}"

# Verify backup
if [ -f "${BACKUP_FILE}" ]; then
    echo "Backup completed: ${BACKUP_FILE}"
    echo "Backup size: $(du -h "${BACKUP_FILE}" | cut -f1)"
else
    echo "ERROR: Backup failed!"
    exit 1
fi

# Cleanup old backups
find "${BACKUP_DIR}" -name "*.sql.gz" -mtime +${RETENTION_DAYS} -delete
echo "Old backups cleaned up (${RETENTION_DAYS} days retention)"

# Upload to S3 (optional)
# aws s3 cp "${BACKUP_FILE}" s3://specgen-backups/postgres/
```

### 6. Health Check Script

Create `backend/db/health.py`:

```python
import asyncpg
import redis
import asyncpg

async def check_postgres_health() -> dict:
    """Check PostgreSQL database health."""
    try:
        conn = await asyncpg.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "6432")),
            user=os.getenv("POSTGRES_USER", "specgen"),
            password=os.getenv("POSTGRES_PASSWORD", "password"),
            database=os.getenv("POSTGRES_DB", "specgen"),
        )
        
        # Execute health check query
        version = await conn.fetchval("SELECT version()")
        await conn.close()
        
        return {
            "status": "healthy",
            "database": "postgresql",
            "version": version,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "postgresql",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

async def check_connection_pool_health():
    """Check connection pool health."""
    pool = get_connection_pool()
    try:
        # Check pool status
        pool_size = pool.get_size()
        available = pool.get_available()
        overflow = pool.get_overflow()
        
        return {
            "status": "healthy",
            "pool_size": pool_size,
            "available_connections": available,
            "overflow_connections": overflow,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }
```

### 7. Performance Tuning Recommendations

Add to `infrastructure/postgres-tuning.conf`:

```ini
# Memory Settings
shared_buffers = 256MB                  # 25% of RAM
effective_cache_size = 768MB            # 75% of RAM
work_mem = 16MB                         # For complex queries
maintenance_work_mem = 128MB            # For maintenance operations
wal_buffers = 16MB                      # Write-Ahead Log buffers

# Connection Settings
max_connections = 200
tcp_keepalives_idle = 60
tcp_keepalives_interval = 10
tcp_keepalives_count = 5

# Query Optimization
random_page_cost = 1.1                 # For SSD storage
effective_io_concurrency = 200         # For SSD storage
default_statistics_target = 100

# Write Ahead Log
wal_level = replica
checkpoint_completion_target = 0.9
max_wal_size = 1GB
min_wal_size = 80MB

# Logging
log_min_duration_statement = 1000       # Log slow queries
log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d '
log_lock_waits = on
log_temp_files = 0

# Autovacuum
autovacuum = on
autovacuum_max_workers = 4
autovacuum_naptime = 30
autovacuum_vacuum_scale_factor = 0.05
autovacuum_analyze_scale_factor = 0.025
```

### 8. Monitoring Configuration

Create `infrastructure/prometheus-postgres.yml`:

```yaml
scrape_configs:
  - job_name: 'postgres'
    static_configs:
      - targets: ['localhost:5432']
    metrics_path: '/metrics'
    relabel_configs:
      - source_labels: [__address__]
        target_label: instance
        regex: '(.+):\\d+'
        replacement: '${1}'
```

### 9. Files to Create

| File | Purpose |
|------|---------|
| `infrastructure/docker-compose.postgres.yml` | Docker Compose for PostgreSQL + PgBouncer |
| `.env.example` | Environment variable template |
| `backend/db/connection.py` | SQLAlchemy async connection configuration |
| `backend/db/init_schema.py` | Database schema initialization |
| `infrastructure/backup-postgres.sh` | Backup script with retention |
| `backend/db/health.py` | Health check endpoints |
| `infrastructure/postgres-tuning.conf` | PostgreSQL performance tuning |
| `infrastructure/prometheus-postgres.yml` | Prometheus monitoring config |

### 10. Implementation Steps

1. **Create infrastructure directory structure**
2. **Write Docker Compose configuration** for PostgreSQL + PgBouncer
3. **Configure environment variables** with secure defaults
4. **Implement async SQLAlchemy connection** with pooling
5. **Create database schema** with all required tables
6. **Add backup and recovery** procedures
7. **Implement health check endpoints**
8. **Configure monitoring** with Prometheus
9. **Test connection pooling** under load
10. **Document all configurations**

### 11. Dependencies

- Docker 20.10+
- Docker Compose 2.0+
- PostgreSQL 15+
- PgBouncer 1.20+
- Python 3.11+ with asyncpg and SQLAlchemy

### 12. Security Considerations

- [ ] Use strong passwords or secrets management
- [ ] Enable SSL/TLS for all connections
- [ ] Restrict network access to database port
- [ ] Use least privilege for database users
- [ ] Enable audit logging
- [ ] Regular security patching
- [ ] Backup encryption

---

**Status**: Planning Complete
**Next Steps**: Implementation in Code mode
**Estimated Files**: 9 files
**Complexity**: Medium
