import json
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import router

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="BUP GridWise LLM Energy Optimizer",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)


def _serialize_errors(errors) -> list:
    cleaned = []
    for err in errors:
        item = {}
        for key, value in err.items():
            if key == "ctx":
                item[key] = {
                    k: (str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v)
                    for k, v in value.items()
                } if isinstance(value, dict) else str(value)
            else:
                item[key] = value
        cleaned.append(item)
    return cleaned


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    if any(e.get("type") == "json_invalid" for e in errors):
        return JSONResponse(status_code=400, content={"detail": "malformed JSON body"})
    return JSONResponse(
        status_code=422,
        content={"detail": "request failed validation", "errors": _serialize_errors(errors)},
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500, content={"detail": "internal processing error"}
    )


app.include_router(router)