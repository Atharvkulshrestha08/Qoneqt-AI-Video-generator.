FROM python:3.11-slim

# Install system dependencies including FFmpeg and TrueType fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-dejavu-core \
    fonts-freefont-ttf \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set up user for Hugging Face Spaces (UID 1000)
RUN useradd -m -u 1000 user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

WORKDIR /app

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Set up writeable directories for any deployment container environment
RUN mkdir -p /app/jobs /app/static /app/output && \
    chown -R 1000:1000 /app && \
    chmod -R 777 /app/jobs /app/output

USER 1000

# Default Hugging Face Spaces port is 7860, Render uses PORT env var
EXPOSE 7860
ENV PORT=7860

CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT:-7860}"]
