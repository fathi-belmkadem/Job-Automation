# Keep this tag in sync with the `playwright` version pinned in requirements.txt —
# Playwright requires the installed Python package to exactly match the browser
# binaries baked into the image, or browser.launch() fails at runtime.
FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# The base image already ships a non-root user at UID/GID 1000 (pwuser) —
# reused here rather than creating a new one, since Kubernetes' fsGroup on
# the mounted PVC/Secret volumes must match whatever UID actually runs this
# container, and 1000 is also the conventional non-root UID the Helm chart
# assumes.
RUN mkdir -p /app/output /app/debug \
    && chown -R pwuser:pwuser /app \
    && chmod +x /app/docker-entrypoint.sh \
    && mkdir -p /tmp/.X11-unix \
    && chmod 1777 /tmp/.X11-unix
USER pwuser

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:5000/healthz || exit 1

CMD ["/app/docker-entrypoint.sh"]
