# MetroFlow Deployment & Production Operations Guide

## Overview

MetroFlow is designed for high availability and rapid containerized deployment across on-premises infrastructure, private transit command centers, and public clouds (AWS, GCP, Azure).

---

## 1. System Requirements

### Hardware Requirements
- **CPU:** 4+ Cores (x86_64 or ARM64)
- **RAM:** 8 GB minimum (16 GB recommended for full GTFS memory mapping and ML inference)
- **Storage:** 20 GB SSD

### Software Dependencies
- **Docker Engine:** 24.0+
- **Docker Compose:** 2.20+
- **Host OS:** Linux (Ubuntu 22.04 LTS / Debian 12 / RHEL 9), macOS, or Windows Server with WSL2

---

## 2. Docker Compose Deployment (Recommended)

### Step 1: Clone Repository & Configure Environment
```bash
git clone https://github.com/organization/Powered-Public-Transit-Route-Optimization.git
cd Powered-Public-Transit-Route-Optimization
cp .env.example .env
```

Review and update `.env`:
```ini
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_postgres_password
POSTGRES_SERVER=db
POSTGRES_PORT=5432
POSTGRES_DB=transit
JWT_SECRET_KEY=generate_a_64_char_random_secret_key
ADMIN_EMAIL=admin@transit.org
ADMIN_PASSWORD=SuperAdminPassword#2026
```

### Step 2: Build and Launch Containers
```bash
docker-compose up -d --build
```

### Step 3: Verify Container Health
```bash
docker-compose ps
```
All three services should be running:
1. `metroflow-postgres` (Port 5432)
2. `metroflow-backend` (Port 8000)
3. `metroflow-frontend` (Port 3000)

### Step 4: Ingest GTFS Dataset (One-Time Setup)
```bash
docker-compose exec backend python -m backend.scripts.ingest_gtfs
docker-compose exec backend python -m backend.scripts.seed_data
```

---

## 3. Cloud Production Architectures

### 3.1 AWS Architecture (ECS Fargate + RDS PostgreSQL)
- **Database:** Amazon RDS for PostgreSQL 15 (Multi-AZ enabled for HA).
- **Backend Service:** Amazon ECS Fargate running `backend:latest` with Application Load Balancer (ALB).
- **Frontend Service:** Amazon S3 + CloudFront CDN (or ECS Nginx container).
- **Secrets Management:** AWS Secrets Manager for `JWT_SECRET_KEY` and DB credentials.
- **WebSocket Scaling:** AWS ALB supports native WebSocket upgrading with 60-second idle timeouts.

### 3.2 Google Cloud Architecture (Cloud Run + Cloud SQL)
- **Database:** Cloud SQL for PostgreSQL 15.
- **Backend:** Google Cloud Run (min instances: 1, concurrency: 80).
- **Frontend:** Cloud Storage bucket with Cloud CDN or Cloud Run service.

### 3.3 Kubernetes Deployment (K8s)
Deployments, Services, and Ingress manifests:
- Standard Ingress with SSL termination (`cert-manager` Let's Encrypt).
- Horizontal Pod Autoscaler (HPA) configured on CPU/memory usage (>75%).
- Persistent Volume Claim (PVC) for PostgreSQL if self-hosted.

---

## 4. Monitoring & Backup Protocols

### Database Backup
```bash
docker-compose exec -t db pg_dump -U postgres transit | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz
```

### Health Check Endpoint
- Monitoring tools (Datadog, Prometheus, UptimeRobot) should query:
  `http://<domain>/health`
- Expected Response: `{"status": "healthy", "service": "MetroFlow Transit Platform", "database": "transit"}`

### Logging
- View live application logs:
```bash
docker-compose logs -f backend
```

