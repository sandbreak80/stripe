FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    make \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml ./

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir poetry && \
    poetry config virtualenvs.create false && \
    poetry install

# Set PYTHONPATH
ENV PYTHONPATH=/app/src

# Copy application code
COPY src/ ./src/
COPY tests/ ./tests/
COPY alembic.ini ./
COPY alembic/ ./alembic/
COPY Makefile ./

# Create artifacts directory
RUN mkdir -p /app/artifacts

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "billing_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
