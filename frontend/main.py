import json
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from livekit import api

load_dotenv()

app = FastAPI(
    title="SwasthyaVaani — ASHA Voice Register",
    description="Zero-build static PWA and LiveKit token service for SwasthyaVaani.",
)

# Enable CORS for local cross-port testing and mobile access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).resolve().parent / "static"


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/sw.js")
def service_worker() -> FileResponse:
    """Serve service worker from root with Service-Worker-Allowed header."""
    return FileResponse(
        STATIC_DIR / "sw.js",
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/"},
    )


@app.get("/manifest.json")
def pwa_manifest() -> FileResponse:
    """Serve PWA manifest."""
    return FileResponse(
        STATIC_DIR / "manifest.json",
        media_type="application/manifest+json",
    )


@app.get("/token")
def get_livekit_token(
    room: str = Query(
        default="asha-demo",
        pattern=r"^[A-Za-z0-9_-]{1,64}$",
        description="LiveKit room name",
    ),
) -> dict[str, str]:
    """Generate LiveKit room access token for ASHA field worker session."""
    livekit_url = os.getenv("LIVEKIT_URL", "").strip()
    api_key = os.getenv("LIVEKIT_API_KEY", "").strip()
    api_secret = os.getenv("LIVEKIT_API_SECRET", "").strip()

    if not livekit_url or not api_key or not api_secret:
        raise HTTPException(
            status_code=503,
            detail=(
                "LiveKit credentials are not configured on the server. "
                "Set LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET."
            ),
        )

    identity = f"asha-kavita-{uuid.uuid4().hex[:8]}"

    try:
        token = (
            api.AccessToken(api_key, api_secret)
            .with_identity(identity)
            .with_name("ASHA Kavita (Ward 4)")
            .with_grants(
                api.VideoGrants(
                    room_join=True,
                    room=room,
                    can_publish=True,
                    can_subscribe=True,
                    can_publish_data=True,
                )
            )
            .to_jwt()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Failed to generate LiveKit session token.",
        ) from exc

    return {
        "url": livekit_url,
        "token": token,
        "room": room,
        "identity": identity,
    }


# Static files mounted strictly after all @app.get routes
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)

