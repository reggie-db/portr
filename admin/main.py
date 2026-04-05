from datetime import datetime, UTC
import os
from typing import Annotated
from fastapi import Cookie, FastAPI, Request
from fastapi.responses import JSONResponse
from apis import api as api_v1
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore
from apis.security import NotAuthenticated
from config.beats import clear_expired_sessions, clear_unclaimed_connections
from config import settings
from config.database import connect_db, disconnect_db
from utils.exception import PermissionDenied, ServiceError

from fastapi import status
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles


@asynccontextmanager
async def lifespan(app: FastAPI):
    # connect to database
    await connect_db()
    app.state.server_start_time = datetime.now(tz=UTC)
    yield
    # disconnect all db connections
    await disconnect_db()


app = FastAPI(lifespan=lifespan)
app.include_router(api_v1)


scheduler = AsyncIOScheduler()
scheduler.add_job(clear_expired_sessions, "interval", hours=1)
scheduler.add_job(clear_unclaimed_connections, "interval", seconds=10)
scheduler.start()


@app.exception_handler(NotAuthenticated)
async def not_authenticated_exception_handler(
    request: Request, exception: NotAuthenticated
):
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"message": "Not authenticated"},
    )


@app.exception_handler(ServiceError)
async def service_error_exception_handler(request: Request, exception: ServiceError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST, content={"message": exception.message}
    )


@app.exception_handler(PermissionDenied)
async def permission_denied_exception_handler(
    request: Request, exception: PermissionDenied
):
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN, content={"message": exception.message}
    )


app.mount("/static", StaticFiles(directory="static"), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        workers=int(os.environ.get("UVICORN_WORKERS", 2)),
        log_level="info",
    )
