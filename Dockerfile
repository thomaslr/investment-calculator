# Use Python 3.11 slim image for smaller size
FROM python:3.11-slim AS production

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=app.py \
    FLASK_ENV=production

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 80

# Run with gunicorn for production
CMD ["gunicorn", "--bind", "0.0.0.0:80", "--workers", "2", "app:app"]
