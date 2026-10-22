FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    "apscheduler>=3.11.2" \
    "python-dotenv>=1.2.1" \
    "requests>=2.31.0" \
    "slack-bolt>=1.27.0" \
    "psycopg[binary]>=3.2"

# Copy application code
COPY main.py phrases.py db.py ./
COPY assets/iroh ./assets/iroh

# Run the bot
CMD ["python", "main.py"]
