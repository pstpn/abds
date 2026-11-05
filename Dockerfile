FROM python:3.12-slim

WORKDIR /srv

COPY app/ ./app/

CMD ["python3", "-m", "app.main"]
