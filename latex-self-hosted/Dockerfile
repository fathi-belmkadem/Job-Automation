FROM python:3.11.10-slim

# apt-get upgrade pulls in Debian security patches released after this base
# image tag was built (CI's Trivy scan gate has already caught real CVEs
# here — libgnutls30/libssl3 — that upgrade resolves).
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    texlive-latex-base \
    texlive-latex-extra \
    texlive-fonts-recommended \
    texlive-fonts-extra \
    texlive-xetex \
    fontconfig \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install the Raleway font family used by the CV/cover-letter templates
COPY fonts/ /usr/share/fonts/raleway/
RUN fc-cache -fv

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
COPY profile.jpg .

# UID/GID pinned to 1000 to match the fsGroup Kubernetes sets on mounted
# volumes for the other two services (this one has none today, but pinning
# consistently avoids the mismatch biting later if that changes).
RUN groupadd -g 1000 appuser && useradd -u 1000 -g appuser -d /app -M appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5000/healthz || exit 1

CMD ["gunicorn", "-b", "0.0.0.0:5000", "--timeout", "120", "--workers", "2", "app:app"]
