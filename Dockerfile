FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 AERZEN_DATA_DIR=/var/lib/aerzen
WORKDIR /srv/aerzen
COPY requirements.txt /srv/aerzen/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && useradd --system --uid 10001 --create-home app && mkdir -p /var/lib/aerzen && chown app:app /var/lib/aerzen
COPY --chown=app:app app /srv/aerzen/app
COPY --chown=app:app templates /srv/aerzen/templates
COPY --chown=app:app static /srv/aerzen/static
COPY --chown=app:app content /srv/aerzen/content
COPY --chown=app:app deploy/entrypoint.sh /srv/aerzen/entrypoint.sh
USER 10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz',timeout=2)" || exit 1
CMD ["sh", "/srv/aerzen/entrypoint.sh"]
