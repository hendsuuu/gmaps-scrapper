# syntax=docker/dockerfile:1
# -----------------------------------------------------------------
# Stage 1 – install Python dependencies
# -----------------------------------------------------------------
FROM apify/actor-python:3.12 AS builder

WORKDIR /usr/src/app

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && playwright install chromium --with-deps


# -----------------------------------------------------------------
# Stage 2 – runtime image
# -----------------------------------------------------------------
FROM apify/actor-python:3.12

# Install Playwright system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /root/.cache/ms-playwright /root/.cache/ms-playwright

# Copy source
COPY . .

CMD ["python", "-m", "src.main"]
