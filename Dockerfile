FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=80 \
    WEB_HOST=0.0.0.0 \
    SCRAPE_HEADLESS=1 \
    SCRAPE_MANUAL_LOGIN=0 \
    CHROME_BIN=/usr/bin/chromium \
    CHROMEDRIVER=/usr/bin/chromedriver

RUN apt-get update && apt-get install -y --no-install-recommends \
        chromium \
        chromium-driver \
        fonts-liberation \
        fonts-noto-color-emoji \
        libnss3 \
        libatk-bridge2.0-0 \
        libgtk-3-0 \
        libgbm1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY frontend ./frontend
COPY data ./data
COPY linkedin_activity_scraper.py facebook_activity_scraper.py instagram_activity_scraper.py x_activity_scraper.py ./

EXPOSE 80

CMD ["sh", "-c", "uvicorn app.api:app --host 0.0.0.0 --port ${PORT:-80}"]
