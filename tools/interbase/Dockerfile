FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY gdb_reader.py web.py ./

EXPOSE 8765

CMD ["python", "web.py", "--host", "0.0.0.0", "--port", "8765", "--database", "/data/BUY.GDB"]
