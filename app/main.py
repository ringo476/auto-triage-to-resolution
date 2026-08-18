# app/main.py
from fastapi import FastAPI

from app.api import webhooks

# 1. Initialize the FastAPI application
app = FastAPI(
    title="SentinelOps AI",
    description="Autonomous DevSecOps & Root Cause Analysis Platform",
    version="1.0.0"
)

# 2. Include the webhook router
# All routes in webhooks.py will now be prefixed with /api
app.include_router(webhooks.router, prefix="/api", tags=["Webhooks"])

# 3. Add a simple health check endpoint (Standard practice)
@app.get("/health")
async def health_check():
    """Simple liveness probe for Docker/Kubernetes."""
    return {"status": "healthy", "service": "SentinelOps AI"}

# 4. Local execution block
if __name__ == "__main__":
    import uvicorn
    # Runs the server on localhost:8000
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)