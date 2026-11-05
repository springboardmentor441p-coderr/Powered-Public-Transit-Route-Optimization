# AI MetroFlow - AI Platform for Metro Crowd Management and Scheduling

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-14+-black.svg)](https://nextjs.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+-blue.svg)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://www.docker.com/)

AI MetroFlow is a comprehensive AI-powered platform for metro crowd management, scheduling optimization, and predictive analytics. Built with modern technologies including FastAPI, Next.js, PostgreSQL, MongoDB, and Redis.

## 🎯 Features

### Core Modules
- **🏢 Station Management** - Real-time station monitoring, congestion tracking, and heatmap visualization
- **🚂 Train Tracking** - Live train positions, occupancy monitoring, and status management
- **📅 Smart Scheduling** - AI-powered schedule optimization, frequency adjustment, and delay handling
- **🧠 AI Predictions** - Crowd forecasting, demand prediction, and traffic pattern analysis
- **🚨 Alert System** - Overcrowding alerts, delay notifications, emergency announcements
- **📊 Analytics Dashboard** - Traffic analytics, station performance, operational monitoring

### Technical Highlights
- **Real-time Updates** - WebSocket/Socket.IO for live data streaming
- **Multi-database Architecture** - PostgreSQL (relational), MongoDB (analytics), Redis (caching)
- **Role-based Access Control** - Admin, Operator, Viewer roles with granular permissions
- **JWT Authentication** - Secure token-based auth with refresh token rotation
- **Docker Ready** - Complete containerization with docker-compose
- **GTFS Data Support** - Import transit data from standard GTFS feeds

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        AI MetroFlow                              │
├─────────────────────────────────────────────────────────────────┤
│  Frontend (Next.js 14)          │  Backend (FastAPI)            │
│  ┌─────────────────────────┐    │  ┌─────────────────────────┐  │
│  │ Dashboard               │    │  │ API v1                  │  │
│  │ Stations/Trains         │◄───┤  │ Auth/Stations/Trains    │  │
│  │ Scheduling              │    │  │ Schedules/Ridership     │  │
│  │ Predictions             │    │  │ Congestion/Alerts       │  │
│  │ Alerts/Analytics        │    │  │ Predictions/Analytics   │  │
│  │ Settings                │    │  │ WebSocket Manager       │  │
│  └─────────────────────────┘    │  └─────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│  PostgreSQL          │  MongoDB         │  Redis               │
│  ┌────────────────┐  │  ┌────────────┐  │  ┌────────────────┐  │
│  │ Users, Lines   │  │  │ Analytics  │  │  │ Caching        │  │
│  │ Stations       │  │  │ Time-series│  │  │ Pub/Sub        │  │
│  │ Trains         │  │  │ Logs       │  │  │ Sessions       │  │
│  │ Schedules      │  │  │            │  │  │ Rate limiting  │  │
│  │ Ridership      │  │  │            │  │  │                │  │
│  └────────────────┘  │  └────────────┘  │  └────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Node.js 20+ (for local frontend development)
- Python 3.12+ (for local backend development)

### Using Docker (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd metroflow

# Copy environment file
cp .env.example .env

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Access applications
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### Local Development

#### Backend
```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp ../.env.example .env

# Run database migrations
alembic upgrade head

# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### Frontend
```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

### Default Credentials
| Role | Email | Password |
|------|-------|----------|
| Admin | admin@metroflow.com | admin123 |
| Operator | operator@metroflow.com | operator123 |
| Viewer | viewer@metroflow.com | viewer123 |

## 📁 Project Structure

```
metroflow/
├── backend/
│   ├── app/
│   │   ├── api/v1/           # API routes
│   │   │   ├── auth.py
│   │   │   ├── stations.py
│   │   │   ├── trains.py
│   │   │   ├── schedules.py
│   │   │   ├── ridership.py
│   │   │   ├── congestion.py
│   │   │   ├── alerts.py
│   │   │   ├── predictions.py
│   │   │   └── analytics.py
│   │   ├── core/             # Core configuration
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   ├── mongodb.py
│   │   │   ├── redis.py
│   │   │   └── security.py
│   │   ├── models/           # SQLAlchemy models
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── services/         # Business logic
│   │   ├── ml/               # ML models
│   │   ├── websocket/        # Real-time communication
│   │   └── main.py           # FastAPI entry point
│   ├── scripts/
│   │   └── load_gtfs_data.py # GTFS data loader
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/              # Next.js App Router pages
│   │   │   ├── dashboard/
│   │   │   ├── stations/
│   │   │   ├── trains/
│   │   │   ├── scheduling/
│   │   │   ├── predictions/
│   │   │   ├── alerts/
│   │   │   ├── analytics/
│   │   │   ├── settings/
│   │   │   └── login/
│   │   ├── components/       # Reusable components
│   │   ├── lib/              # Utilities & API client
│   │   ├── hooks/            # Custom React hooks
│   │   └── styles/           # Global styles
│   ├── public/
│   ├── package.json
│   ├── Dockerfile
│   └── Dockerfile.prod
├── nginx/
│   └── nginx.conf
├── docker-compose.yml
├── docker-compose.prod.yml
├── .env.example
└── README.md
```

## 🔧 API Endpoints

### Authentication
- `POST /api/v1/auth/login` - User login
- `POST /api/v1/auth/register` - User registration
- `POST /api/v1/auth/refresh` - Refresh access token
- `POST /api/v1/auth/logout` - Logout
- `GET /api/v1/auth/me` - Current user profile

### Stations & Lines
- `GET /api/v1/stations/lines` - List lines
- `POST /api/v1/stations/lines` - Create line
- `GET /api/v1/stations` - List stations
- `POST /api/v1/stations` - Create station
- `GET /api/v1/stations/{id}/congestion` - Station congestion
- `GET /api/v1/stations/{id}/heatmap` - Congestion heatmap

### Trains
- `GET /api/v1/trains` - List trains
- `POST /api/v1/trains` - Create train
- `GET /api/v1/trains/{id}/occupancy` - Train occupancy

### Schedules
- `GET /api/v1/schedules` - List schedules
- `GET /api/v1/schedules/train/{id}` - Train schedule
- `GET /api/v1/schedules/station/{id}` - Station schedule
- `POST /api/v1/schedules/optimize` - AI schedule optimization

### Predictions
- `POST /api/v1/predictions/crowd` - Crowd prediction
- `GET /api/v1/predictions/demand` - Demand forecast
- `GET /api/v1/predictions/traffic/station/{id}` - Traffic patterns

### Alerts
- `GET /api/v1/alerts` - List alerts
- `GET /api/v1/alerts/summary` - Alert summary
- `POST /api/v1/alerts/{id}/read` - Mark as read
- `POST /api/v1/alerts/{id}/dismiss` - Dismiss alert

### Analytics
- `GET /api/v1/analytics/traffic` - Traffic analytics
- `GET /api/v1/analytics/station-performance` - Station performance
- `GET /api/v1/analytics/operational` - Operational monitoring

## 🤖 AI/ML Models

### Implemented Models
1. **Crowd Density Estimation** - Ridge Regression on historical ridership data
2. **Congestion Prediction** - Time-series forecasting for station congestion
3. **Demand Forecasting** - Random Forest for passenger demand prediction
4. **Traffic Pattern Analysis** - Hourly/daily pattern recognition
5. **Schedule Optimization** - Genetic algorithm for frequency optimization

### Model Retraining
```bash
# Via API
POST /api/v1/predictions/retrain
{
  "model_type": "all",
  "force": true
}
```

## 📊 GTFS Data Import

Import standard GTFS transit feeds:

```bash
# Load GTFS data from directory
python backend/scripts/load_gtfs_data.py /path/to/gtfs/directory
```

Supported GTFS files:
- `agency.txt` - Transit agencies
- `routes.txt` - Routes/lines
- `stops.txt` - Stations/stops
- `trips.txt` - Trip patterns
- `stop_times.txt` - Stop schedules
- `calendar.txt` - Service calendars
- `shapes.txt` - Route geometries

## 🐳 Docker Deployment

### Development
```bash
docker-compose up -d
```

### Production
```bash
# Set production environment variables
export POSTGRES_USER=your_user
export POSTGRES_PASSWORD=secure_password
export SECRET_KEY=your-32-char-secret-key
export CORS_ORIGINS='["https://yourdomain.com"]'

# Deploy
docker-compose -f docker-compose.prod.yml up -d
```

## 🔐 Security

- JWT-based authentication with short-lived access tokens
- Refresh token rotation with database storage
- Role-based access control (Admin, Operator, Viewer)
- Password hashing with bcrypt
- CORS configuration
- SQL injection prevention via SQLAlchemy ORM
- Rate limiting ready (Redis-backed)

## 🧪 Testing

```bash
# Backend tests
cd backend
pytest -v --cov=app

# Frontend tests
cd frontend
npm test
```

## 📈 Monitoring

- Health check: `GET /health`
- API documentation: `GET /docs` (Swagger UI)
- ReDoc: `GET /redoc`
- Prometheus metrics ready (add prometheus-client)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Branch Naming
- Feature: `feature/description`
- Bugfix: `fix/description`
- Hotfix: `hotfix/description`

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- GTFS (General Transit Feed Specification) for transit data standard
- FastAPI, Next.js, PostgreSQL, MongoDB, Redis communities
- Open source libraries used throughout the project

## 📞 Support

For questions and support:
- Create an issue on GitHub
- Check the [API Documentation](http://localhost:8000/docs)
- Review the [GTFS Specification](https://gtfs.org/)

---

**Built with ❤️ for smarter urban mobility**