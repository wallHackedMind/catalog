from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader


API_KEY = "test"
api_key_header = APIKeyHeader(name="X-API-Key")


async def check_api_key(api_key: str = Depends(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
