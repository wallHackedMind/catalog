import uvicorn

from fastapi import APIRouter, FastAPI
from catalog.api import router as catalog_router

app = FastAPI()
api_router = APIRouter()


app = FastAPI(
    title="catalog",
    openapi_url=f"/v1/openapi.json",
)
api_router.include_router(catalog_router)
app.include_router(api_router)

if __name__ == "__main__":
    uvicorn.run(app, host="localhost")
