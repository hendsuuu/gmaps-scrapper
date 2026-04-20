from fastapi import FastAPI
from a2wsgi import ASGIMiddleware

app = FastAPI()

@app.get("/")
async def root():
    return {"hello": "world"}

@app.get("/api/health")
async def health():
    return {"status": "ok"}

application = ASGIMiddleware(app)