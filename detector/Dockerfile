FROM python:3.11-slim

WORKDIR /app

# scikit-learn pinned to the training version: the committed Isolation
# Forest pickles are not guaranteed to load across sklearn releases.
RUN pip install --no-cache-dir pydantic scikit-learn==1.7.2

COPY *.py .

# Reads the replay event stream on stdin; see docker-compose.yml for wiring.
CMD ["python", "main.py"]
