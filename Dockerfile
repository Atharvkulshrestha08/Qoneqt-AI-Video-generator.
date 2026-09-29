FROM python:3.11-slim

# Install system dependencies including FFmpeg and TrueType fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-dejavu-core \
    fonts-freefont-ttf \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Ensure jobs and static directories exist
RUN mkdir -p /app/jobs /app/static /app/output

# Default Hugging Face Spaces port is 7860
EXPOSE 7860

ENV PORT=7860

CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT:-7860}"]
