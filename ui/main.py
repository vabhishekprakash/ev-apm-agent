from fastapi import FastAPI

app = FastAPI(title="EV APM UI Service")

@app.get("/")
def root():
    return {"service": "ui", "status": "ok", "message": "Hello from ui"}

@app.get("/health")
def health():
    return {"status": "healthy"}
