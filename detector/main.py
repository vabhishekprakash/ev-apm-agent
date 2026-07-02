from fastapi import FastAPI

app = FastAPI(title="EV APM Detector Service")

@app.get("/")
def root():
    return {"service": "detector", "status": "ok", "message": "Hello from detector"}

@app.get("/health")
def health():
    return {"status": "healthy"}

