FROM python:3.12-slim

# Create non-root user with specific UID for predictable file ownership
ARG UID=1000
ARG GID=1000
RUN groupadd -g ${GID} appuser && useradd -u ${UID} -g ${GID} -m -s /bin/bash appuser

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir fit-file-faker

# Copy source code
COPY src/ ./src/

# Create directories with correct ownership
RUN mkdir -p /app/data/downloaded /app/data/processed /app/data/errors \
    /app/logs /app/state \
    && chown -R appuser:appuser /app

USER appuser

ENTRYPOINT ["python", "-m", "src.main"]
