FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir apscheduler>=3.11.2 python-dotenv>=1.2.1 slack-bolt>=1.27.0 supabase>=2.27.2

# Copy application code
COPY main.py phrases.py ./

# Run the bot
CMD ["python", "main.py"]
