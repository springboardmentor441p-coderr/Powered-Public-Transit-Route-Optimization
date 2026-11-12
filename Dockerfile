FROM node:20-alpine AS web-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
COPY data/reference/cta_bus_routes.geojson ./data/reference/cta_bus_routes.geojson
COPY outputs/reports/ ./outputs/reports/
COPY --from=web-build /app/frontend/dist/ ./frontend/dist/
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["sh", "-c", "uvicorn src.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
