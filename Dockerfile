FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv/app
COPY requirements.txt /srv/app/requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt \
 && groupadd --system --gid 10001 appgroup \
 && useradd --system --uid 10001 --gid appgroup --home-dir /nonexistent appuser \
 && mkdir -p /data && chown -R appuser:appgroup /data
COPY --chown=appuser:appgroup app /srv/app/app
USER appuser
EXPOSE 8000
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000","--proxy-headers","--no-access-log"]
