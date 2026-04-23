"""FastAPI app factory. Run locally: `cd src && python -m uvicorn main:app --host 0.0.0.0 --port 8000`."""

from fastapi import FastAPI

from routers.litigation import router as litigation_router

app = FastAPI(title="Litigation API", version="1.0.0")
app.include_router(litigation_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
