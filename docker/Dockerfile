FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy project files needed for installation
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install Python dependencies (standard includes a2a, cli, crewai, llm, tools, scheduling)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir ".[standard]"

# Create data directory for DuckDB storage (standalone mode)
RUN mkdir -p /app/.data

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

# Expose port
EXPOSE 8000

# Run application via registered entry point
CMD ["apflow-server"]
