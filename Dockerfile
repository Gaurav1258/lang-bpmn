# =============================================================================
# Stage 1: Build Frontend React SPA (studio)
# =============================================================================
FROM node:20-slim AS frontend-builder
WORKDIR /app/studio

# Install dependencies first for layer caching
COPY studio/package*.json ./
RUN npm ci

# Copy studio source code and build production assets
COPY studio/ ./
RUN npm run build

# =============================================================================
# Stage 2: Production Python Runtime (FastAPI + LangGraph)
# =============================================================================
FROM python:3.11-slim AS production

WORKDIR /app

# Install uv for fast, reliable package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy project definition and source code, then install
COPY pyproject.toml README.md ./
COPY agent_bpmn/ /app/agent_bpmn/
RUN uv pip install --system .

# Copy application entrypoint
COPY run_studio.py /app/run_studio.py

# Copy built frontend assets from Stage 1 into studio/dist
COPY --from=frontend-builder /app/studio/dist /app/studio/dist

# Create workflows directory for runtime CRUD
RUN mkdir -p /app/workflows

# Cloud Run injects PORT (default 8080)
ENV PORT=8080
ENV HOST=0.0.0.0
ENV PYTHONUNBUFFERED=1
ENV WORKFLOWS_DIR=/app/workflows

EXPOSE 8080

CMD ["sh", "-c", "uvicorn agent_bpmn.server.app:app --host 0.0.0.0 --port ${PORT}"]
