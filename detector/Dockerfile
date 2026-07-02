FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir pydantic

COPY *.py .

# Reads the replay event stream on stdin; see docker-compose.yml for wiring.
CMD ["python", "main.py"]
