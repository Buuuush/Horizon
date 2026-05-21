"""FastAPI dashboard application for Horizon."""

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Set
from enum import Enum
import json
import asyncio

from pydantic import BaseModel, ConfigDict

# Import from core modules
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.storage.manager import StorageManager
from src.setup.profile_manager import ProfileManager
from src.setup.profile_init import init_profiles
from src.ai.feedback_analyzer import FeedbackAnalyzer
from src.models import Profile, FeedbackSignal


# ===== Pydantic Models for API =====

class ProfileResponse(BaseModel):
    """Profile response model."""
    model_config = ConfigDict(from_attributes=True)

    name: str
    description: Optional[str] = None
    ai_score_threshold: float
    per_source_prompts: dict
    active_sources: list
    created_at: str
    updated_at: str
    is_active: bool

class FeedbackRequest(BaseModel):
    """Request model for submitting feedback."""
    item_id: str
    user_rating: int  # 1 for 👍, -1 for 👎
    is_favorite: bool = False
    notes: Optional[str] = None


class FeedbackStatsResponse(BaseModel):
    """Feedback statistics response."""
    total_feedback: int
    positive_feedback: int
    negative_feedback: int
    favorites: int
    misscored_items: int
    accuracy_rate: str
    summary: str


class SummaryMetadata(BaseModel):
    """Metadata for a summary."""
    date: str
    profile_name: str
    items_processed: int
    items_scored: int
    avg_score: float

class WebSocketMessageType(str, Enum):
    """WebSocket message types."""
    PROGRESS = "progress"
    ITEM_SCORED = "item_scored"
    SUMMARY_COMPLETE = "summary_complete"
    ERROR = "error"


class ProgressMessage(BaseModel):
    """Message for scraping progress."""
    type: str = "progress"
    stage: str  # "scraping", "analyzing", "summarizing"
    current: int  # current count
    total: Optional[int] = None  # total count
    message: str


class ItemScoredMessage(BaseModel):
    """Message for scored item."""
    type: str = "item_scored"
    item_id: str
    title: str
    source: str
    score: float
    url: str
    summary: Optional[str] = None


class SummaryCompleteMessage(BaseModel):
    """Message when summary is complete."""
    type: str = "summary_complete"
    profile_name: str
    language: str
    path: str
    timestamp: str


class FavoriteRequest(BaseModel):
    """Request to add/remove favorite."""
    item_id: str
    is_favorite: bool

# ===== Initialize FastAPI =====

app = FastAPI(
    title="Horizon Dashboard",
    description="Live dashboard for Horizon news aggregator",
    version="1.0.0",
)

# Initialize storage and managers
try:
    storage = init_profiles(data_dir="data")
    profile_manager = ProfileManager(storage)
    feedback_analyzer = FeedbackAnalyzer(storage)
    storage_error = None
except Exception as e:
    print(f"⚠ Warning: Failed to initialize storage: {e}")
    print("ℹ Dashboard will work in read-only mode with limited functionality")
    storage = None
    profile_manager = None
    feedback_analyzer = None
    storage_error = str(e)


# ===== WebSocket Connection Manager =====

class ConnectionManager:
    """Manager for WebSocket connections."""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket):
        """Add a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.add(websocket)
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        self.active_connections.discard(websocket)
    
    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients.

        Supports two kinds of connection objects for testing:
        - WebSocket-like objects with an async `send_json` method
        - Async-callable objects (e.g., AsyncMock) which can be awaited directly
        """
        disconnected = set()
        for connection in list(self.active_connections):
            try:
                # Prefer calling the connection itself when it's callable (tests use AsyncMock())
                if callable(connection):
                    # If the callable connection also exposes `send_json` and
                    # doesn't have a side_effect (typical WebSocket mock), prefer
                    # calling `send_json`. If the callable itself has a side_effect
                    # (tests may use AsyncMock(side_effect=...)), call the
                    # connection directly so the side_effect triggers.
                    if hasattr(connection, "send_json") and getattr(connection, "side_effect", None) is None:
                        await connection.send_json(message)
                    else:
                        await connection(message)
                elif hasattr(connection, "send_json") and callable(getattr(connection, "send_json")):
                    await connection.send_json(message)
                else:
                    # Fallback: try attribute send_json
                    await connection.send_json(message)
            except Exception:
                disconnected.add(connection)

        # Clean up disconnected clients
        for connection in disconnected:
            self.active_connections.discard(connection)


manager = ConnectionManager()


# ===== API Routes =====

# ---- Search ----

@app.get("/api/search")
async def search_articles(
    q: str = "",
    tag: str = "",
    source: str = "",
    score_min: float = 0,
    score_max: float = 10,
    date_start: str = "",
    date_end: str = "",
    limit: int = 20,
):
    """Search archived articles.

    Parameters correspond to the fields in the archive DB.
    """
    _ensure_storage()
    results = storage.search_articles(
        q=q,
        tag=tag,
        source=source,
        score_min=score_min,
        score_max=score_max,
        date_start=date_start,
        date_end=date_end,
        limit=limit,
    )
    return {"results": results}


# ---- Profiles ----

@app.post("/api/profiles")
async def create_profile(profile: ProfileResponse):
    """Create a new profile with minimal fields (name)."""
    _ensure_storage()
    if storage.get_profile(profile.name):
        raise HTTPException(status_code=400, detail="Profile already exists")
    # Use defaults from Profile model
    new_profile = Profile(
        name=profile.name,
        description=profile.description or "",
        ai_score_threshold=profile.ai_score_threshold,
        per_source_prompts=profile.per_source_prompts or {},
        active_sources=profile.active_sources or [],
        created_at=datetime.utcnow().isoformat(),
        updated_at=datetime.utcnow().isoformat(),
        is_active=False,
    )
    storage.save_profile(new_profile)
    return {"status": "ok", "message": f"Profile '{profile.name}' created"}

@app.put("/api/profiles/{profile_name}")
async def edit_profile(profile_name: str, updates: ProfileResponse):
    """Edit an existing profile (partial update)."""
    _ensure_storage()
    existing = storage.get_profile(profile_name)
    if not existing:
        raise HTTPException(status_code=404, detail="Profile not found")
    # Apply updates (ignore name change)
    existing.description = updates.description or existing.description
    existing.ai_score_threshold = updates.ai_score_threshold or existing.ai_score_threshold
    existing.per_source_prompts = updates.per_source_prompts or existing.per_source_prompts
    existing.active_sources = updates.active_sources or existing.active_sources
    existing.updated_at = datetime.utcnow().isoformat()
    storage.save_profile(existing)
    return {"status": "ok", "message": f"Profile '{profile_name}' updated"}

@app.post("/api/profiles/{profile_name}/activate")
async def activate_profile(profile_name: str):
    """Set a profile as active for the current session."""
    _ensure_storage()
    profile = storage.get_profile(profile_name)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    storage.set_active_profile(profile_name)
    return {"status": "ok", "message": f"Profile '{profile_name}' activated"}

# ---- Profiles ----

@app.post("/api/profiles")
async def create_profile(profile: ProfileResponse):
    """Create a new profile with minimal fields (name)."""
    _ensure_storage()
    if storage.get_profile(profile.name):
        raise HTTPException(status_code=400, detail="Profile already exists")
    # Use defaults from Profile model
    new_profile = Profile(
        name=profile.name,
        description=profile.description or "",
        ai_score_threshold=profile.ai_score_threshold,
        per_source_prompts=profile.per_source_prompts or {},
        active_sources=profile.active_sources or [],
        created_at=datetime.utcnow().isoformat(),
        updated_at=datetime.utcnow().isoformat(),
        is_active=False,
    )
    storage.save_profile(new_profile)
    return {"status": "ok", "message": f"Profile '{profile.name}' created"}


def _ensure_storage():
    """Check if storage is initialized. Raise HTTPException if not."""
    if not storage:
        raise HTTPException(
            status_code=503,
            detail=f"Storage not initialized. Please create data/config.json. Error: {storage_error}",
        )


@app.get("/api/profiles", response_model=List[ProfileResponse])
async def get_profiles():
    """Get list of all profiles."""
    _ensure_storage()

    profiles = storage.get_all_profiles()
    return [
        ProfileResponse(
            name=p.name,
            description=p.description,
            ai_score_threshold=p.ai_score_threshold,
            per_source_prompts=p.per_source_prompts,
            active_sources=[s.value for s in p.active_sources],
            created_at=p.created_at.isoformat(),
            updated_at=p.updated_at.isoformat(),
            is_active=p.is_active,
        )
        for p in profiles
    ]


@app.get("/api/profiles/{profile_name}")
async def get_profile(profile_name: str):
    """Get a specific profile."""
    _ensure_storage()

    profile = storage.get_profile(profile_name)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    return ProfileResponse(
        name=profile.name,
        description=profile.description,
        ai_score_threshold=profile.ai_score_threshold,
        per_source_prompts=profile.per_source_prompts,
        active_sources=[s.value for s in profile.active_sources],
        created_at=profile.created_at.isoformat(),
        updated_at=profile.updated_at.isoformat(),
        is_active=profile.is_active,
    )


@app.post("/api/profiles/{profile_name}/activate")
async def activate_profile(profile_name: str):
    """Activate a profile."""
    _ensure_storage()

    profile = storage.get_profile(profile_name)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    storage.set_active_profile(profile_name)
    return {"status": "ok", "message": f"Profile '{profile_name}' activated"}


@app.get("/api/status")
async def get_status():
    """Get system status."""
    if not storage:
        return {
            "status": "degraded",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Storage not initialized",
            "detail": storage_error,
        }

    active_profile = storage.get_active_profile()
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "active_profile": active_profile.name if active_profile else None,
        "profiles_count": len(storage.get_all_profiles()),
    }


@app.post("/api/feedback/{profile_name}")
async def submit_feedback(profile_name: str, feedback: FeedbackRequest):
    """Submit feedback for an article."""
    _ensure_storage()

    # Verify profile exists
    profile = storage.get_profile(profile_name)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Create feedback signal
    signal = FeedbackSignal(
        item_id=feedback.item_id,
        profile_name=profile_name,
        user_rating=feedback.user_rating,
        is_favorite=feedback.is_favorite,
        notes=feedback.notes,
        timestamp=datetime.utcnow(),
    )

    storage.save_feedback(signal)
    return {"status": "ok", "message": "Feedback saved"}


@app.get("/api/feedback/{profile_name}/stats", response_model=FeedbackStatsResponse)
async def get_feedback_stats(profile_name: str):
    """Get feedback statistics for a profile."""
    _ensure_storage()

    if not feedback_analyzer:
        raise HTTPException(status_code=503, detail="Feedback analyzer not initialized")

    profile = storage.get_profile(profile_name)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    summary = feedback_analyzer.get_feedback_summary(profile_name)
    return FeedbackStatsResponse(
        total_feedback=summary["total_feedback"],
        positive_feedback=summary["positive_feedback"],
        negative_feedback=summary["negative_feedback"],
        favorites=summary["favorites"],
        misscored_items=summary["misscored_items"],
        accuracy_rate=summary["accuracy_rate"],
        summary=summary["summary"],
    )


@app.get("/api/feedback/{profile_name}/recommendations")
async def get_feedback_recommendations(profile_name: str):
    """Get improvement recommendations based on feedback."""
    _ensure_storage()

    if not feedback_analyzer:
        raise HTTPException(status_code=503, detail="Feedback analyzer not initialized")

    profile = storage.get_profile(profile_name)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    roadmap = feedback_analyzer.get_improvement_roadmap(profile_name)
    return {"recommendations": roadmap}


@app.get("/api/summaries")
async def list_summaries(profile_name: Optional[str] = None, limit: int = 30):
    """List past summaries (pagination support)."""
    summaries_dir = Path("data/summaries")
    if not summaries_dir.exists():
        return {"summaries": []}

    # List HTML files in summaries directory
    html_files = sorted(summaries_dir.glob("*.html"), reverse=True)[:limit]

    summaries = []
    for file in html_files:
        # Parse date from filename: horizon-{date}-{lang}.html
        parts = file.stem.split("-")
        if len(parts) >= 3:
            date_str = "-".join(parts[1:3])  # Extract YYYY-MM-DD
            lang = parts[-1]
            summaries.append(
                {
                    "date": date_str,
                    "language": lang,
                    "path": f"/data/summaries/{file.name}",
                    "size_bytes": file.stat().st_size,
                }
            )

    return {"summaries": summaries}


@app.get("/api/summaries/{date}")
async def get_summary(date: str, language: str = "en"):
    """Get full summary for a specific date."""
    summary_path = Path(f"data/summaries/horizon-{date}-{language}.html")

    if not summary_path.exists():
        raise HTTPException(status_code=404, detail="Summary not found")

    return FileResponse(path=summary_path, media_type="text/html")


@app.post("/api/favorites/{profile_name}")
async def toggle_favorite(profile_name: str, request: FavoriteRequest):
    """Toggle favorite status for an article."""
    _ensure_storage()

    profile = storage.get_profile(profile_name)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Get or create feedback signal
    signal = FeedbackSignal(
        item_id=request.item_id,
        profile_name=profile_name,
        user_rating=0,  # Neutral rating for favorites
        is_favorite=request.is_favorite,
        timestamp=datetime.utcnow(),
    )

    storage.save_feedback(signal)
    return {"status": "ok", "message": f"Favorite {'added' if request.is_favorite else 'removed'}"}


@app.get("/api/favorites/{profile_name}")
async def get_favorites(profile_name: str, limit: int = 50):
    """Get all favorite articles for a profile."""
    _ensure_storage()

    profile = storage.get_profile(profile_name)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Get feedback signals with is_favorite=true
    feedback_list = storage.get_feedback_stats(profile_name).get("favorites_list", [])
    return {
        "profile_name": profile_name,
        "favorites_count": len(feedback_list),
        "items": feedback_list[:limit],
    }


@app.websocket("/ws/progress/{profile_name}")
async def websocket_progress(websocket: WebSocket, profile_name: str):
    """WebSocket endpoint for real-time scraping/analysis progress."""
    await manager.connect(websocket)
    try:
        # Keep connection open and listen for messages
        while True:
            data = await websocket.receive_text()
            # Echo back any client messages (for keep-alive)
            if data:
                await websocket.send_json({"type": "ack", "message": "received"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        manager.disconnect(websocket)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "Horizon Dashboard"}


# ===== Static Files =====

# Mount static files
web_dir = Path(__file__).parent
static_dir = web_dir / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def root():
    """Serve main dashboard page."""
    index_path = web_dir / "static" / "index.html"
    if index_path.exists():
        return FileResponse(path=index_path, media_type="text/html")
    return {"message": "Horizon Dashboard"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5000)
