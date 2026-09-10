FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY seed_admin_data.py .

# Seed data for seed_admin_data.py ONLY — NOT servable. Do not add this to
# STATIC_DIR/app/static: it's Tim's real historical lab results + genome
# findings, and once any other user is invited, Cloudflare Access gates the
# whole hostname, not individual paths, so anything under the static tree
# becomes reachable by them.
COPY data ./data

# The actual servable tree: just the hub and the one real app. Deliberately
# does NOT include apps/blood-test-dashboard.html or apps/genome-dashboard.html
# (Tim's real historical labs / raw 23andMe SNP data) — those stay in the
# repo (never delete Tim's files) but must never be copied into the image.
COPY index.html ./static/index.html
COPY apps/peptide-tracker.html ./static/apps/peptide-tracker.html
COPY assets ./static/assets

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=4)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
