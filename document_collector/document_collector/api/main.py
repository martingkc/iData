from fastapi import FastAPI
import uvicorn
import os
from threading import Thread

# debug only - adjust the path to import modules correctly

from document_collector.api.rclone_service.router import (
    router as rclone_router,
)

from fastapi.middleware.cors import CORSMiddleware
from document_collector.metadata_handlers.folder_watchdog import start_folder_watchdog

# Start the folder watchdog in a separate thread
app = FastAPI()

# Start the folder watchdog in a separate thread
watchdog_thread = Thread(target=start_folder_watchdog, daemon=True)
watchdog_thread.start()
# Dev CORS: allow the Vite dev server by default.
# Tighten this for production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rclone_router, prefix="/rclone", tags=["rclone"])


@app.get("/")
async def root():
    return {"message": "Document Collector API is running."}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
