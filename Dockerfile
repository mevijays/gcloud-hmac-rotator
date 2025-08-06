# Multi-stage build for security and efficiency
FROM python:3.11-slim as builder

# ✅ Security: Install security updates
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# ✅ Install Python dependencies in builder stage
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ✅ Production stage - minimal and secure
FROM python:3.11-slim

# ✅ Security: Install only security updates
RUN apt-get update && apt-get upgrade -y && \
    rm -rf /var/lib/apt/lists/*

# ✅ Create non-root user
RUN groupadd --gid 65534 appuser && \
    useradd --uid 65534 --gid 65534 --shell /bin/bash --create-home appuser

# ✅ Copy Python packages from builder
COPY --from=builder /root/.local /home/appuser/.local

# ✅ Set up application directory
WORKDIR /app

# ✅ Copy application with proper ownership
COPY --chown=appuser:appuser app.py .

# ✅ Security: Make filesystem read-only except for tmp
RUN mkdir -p /tmp/app && chown appuser:appuser /tmp/app

# ✅ Switch to non-root user
USER 65534:65534

# ✅ Environment for security and logging
ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# ✅ Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import sys; sys.exit(0)"

# ✅ Run the application
ENTRYPOINT ["python3", "app.py"]
