# ---- stage 1: build the React frontend
FROM node:20-slim AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- stage 2: Python API + built frontend
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
COPY --from=web /web/dist ./frontend/dist
EXPOSE 8000
# first start trains the models automatically if outputs/ and models/ are missing
CMD ["sh", "-c", "uvicorn server.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
