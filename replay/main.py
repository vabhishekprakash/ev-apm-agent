from fastapi import FastAPI

app = FastAPI(title="EV APM Replay Service")

@app.get("/")
def root():
    return {"service": "replay", "status": "ok", "message": "Hello from replay"}

@app.get("/health")
def health():
    return {"status": "healthy"}
