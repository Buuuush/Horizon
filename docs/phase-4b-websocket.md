# Phase 4B: WebSocket Broadcasting & Real-time Progress

## Overview

Phase 4B implements real-time progress broadcasting from the orchestrator to connected WebSocket clients. This allows the dashboard to display live scraping, analysis, and summary generation progress.

## Architecture

### WebSocket Flow

```
Browser → Dashboard UI (localhost:5000)
                ↓
        WebSocket Connection
        /ws/progress/{profile}
                ↓
        ConnectionManager (in web app)
                ↓
        CLI Process (running orchestrator.run())
                ↓
        Broadcasts progress messages
```

### Message Broadcasting

When the orchestrator runs:

1. **Scraping Stage** - After fetching all sources:
```python
{
  "type": "progress",
  "stage": "scraping",
  "current": 42,
  "total": 42,
  "message": "Scraped 42 items from all sources"
}
```

2. **Scoring Stage** - For each item passing the threshold:
```python
{
  "type": "item_scored",
  "item_id": "hn:12345",
  "title": "Breakthrough in AI...",
  "source": "hackernews",
  "score": 8.5,
  "url": "https://news.ycombinator.com/item?id=12345",
  "summary": "Optional AI-generated summary"
}
```

3. **Summary Stage** - When summary is complete:
```python
{
  "type": "summary_complete",
  "profile_name": "ml-research",
  "language": "bilingual",
  "path": "/app/data/summaries/2026-05-05-summary.html",
  "timestamp": "2026-05-05T14:30:00Z",
  "items_count": 15
}
```

## Implementation Details

### Orchestrator Changes

**File**: `src/orchestrator.py`

**New Constructor Parameter**:
```python
def __init__(
    self,
    config: Config,
    storage: StorageManager,
    profile: Optional[Profile] = None,
    broadcast_callback: Optional[Callable[[Dict[str, Any]], Any]] = None,
):
    self.broadcast_callback = broadcast_callback
```

**New Broadcast Method**:
```python
async def _broadcast(self, message: Dict[str, Any]) -> None:
    """Broadcast a progress message to WebSocket clients."""
    if self.broadcast_callback:
        try:
            if asyncio.iscoroutinefunction(self.broadcast_callback):
                await self.broadcast_callback(message)
            else:
                self.broadcast_callback(message)
        except Exception as e:
            # Silently ignore broadcast errors
            self.console.print(f"[dim]ℹ️  WebSocket broadcast failed: {e}[/dim]")
```

**Broadcast Calls Added**:
- After `fetch_all_sources()` - "progress" with stage="scraping"
- After `_analyze_content()` - "progress" with stage="analyzing"
- For each item passing threshold - "item_scored" messages
- After summary generation - "summary_complete" message

### CLI Integration

**File**: `src/main.py`

When running from CLI, the orchestrator checks if the web app module is loaded:

```python
broadcast_callback = None
try:
    if 'src.web.app' in sys.modules:
        from .web.app import manager
        broadcast_callback = manager.broadcast
except Exception:
    pass

orchestrator = HorizonOrchestrator(
    config,
    storage,
    profile=profile,
    broadcast_callback=broadcast_callback,
)
```

### WebSocket Connection Manager

**File**: `src/web/app.py`

The `ConnectionManager` broadcasts to all connected clients:

```python
class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
    
    async def broadcast(self, message: dict):
        """Broadcast to all connected clients."""
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.add(connection)
        
        for connection in disconnected:
            self.active_connections.discard(connection)
```

## Usage Scenarios

### Scenario 1: CLI Only (No Broadcasting)

```bash
# Run orchestrator from terminal
$ python -m src.main --profile ml-research

[yellow]⚠️  Aucun profil sélectionné[/yellow]
📊 Profil actif: ml-research (seuil: 7.5)
📥 42 éléments récupérés...
🤖 42 éléments analysés...
⭐️ 15 éléments notés ≥ 7.5
📝 Génération du résumé...
💾 Résumé enregistré...
```

Result: No broadcasting, pipeline runs normally

### Scenario 2: Dashboard + CLI (With Broadcasting)

**Terminal 1 - Dashboard**:
```bash
$ python -m uvicorn src.web.app:app --host 0.0.0.0 --port 5000
INFO:     Uvicorn running on http://0.0.0.0:5000
```

**Terminal 2 - Orchestrator**:
```bash
$ python -m src.main --profile ml-research

📊 Profil actif: ml-research (seuil: 7.5)
📥 42 éléments récupérés...
🤖 42 éléments analysés...
⭐️ 15 éléments notés ≥ 7.5
📝 Génération du résumé...
💾 Résumé enregistré...
```

**Browser - Dashboard (localhost:5000)**:
- Shows live progress updates
- Articles appear as they're scored
- Progress bar updates
- Summary displays when ready

### Scenario 3: Docker Compose (Both in Same Stack)

```bash
# In future Phase 5, both services run together:
docker-compose up

# Dashboard: localhost:5000
# Orchestrator: runs as cron job or scheduled task
```

## Frontend Integration

### JavaScript WebSocket Connection

```javascript
// Connect to WebSocket endpoint
const ws = new WebSocket(`ws://localhost:5000/ws/progress/${profileName}`);

ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    
    if (message.type === 'progress') {
        // Update progress bar
        updateProgress(message.current, message.total);
    } else if (message.type === 'item_scored') {
        // Add article to list
        addArticleToList(message);
    } else if (message.type === 'summary_complete') {
        // Summary ready, show notification
        showSummaryComplete(message);
    }
};
```

## Error Handling

**Broadcast Failures Don't Block Pipeline**:
- If WebSocket connection fails, orchestrator continues
- Error message logged: "WebSocket broadcast failed: {error}"
- Pipeline completes normally even if broadcasting fails

**Missing Web App Module**:
- If dashboard not running, `broadcast_callback` is None
- Orchestrator checks `if self.broadcast_callback:` before broadcasting
- Graceful degradation - works with or without dashboard

## Testing

### Unit Tests

See `tests/test_phase4_integration.py`:
- Test profile system integration
- Test feedback learning
- Test cache management

### Integration Test (WebSocket Broadcasting)

```python
# Manual test: Start dashboard, run orchestrator
# Check browser console for WebSocket messages

async def test_broadcast_functionality():
    """Test that orchestrator can broadcast messages."""
    manager = ConnectionManager()
    
    # Create mock WebSocket
    mock_ws = AsyncMock()
    await manager.connect(mock_ws)
    
    # Broadcast message
    message = {"type": "progress", "stage": "scraping"}
    await manager.broadcast(message)
    
    # Verify message sent
    mock_ws.send_json.assert_called_with(message)
```

## Configuration

No additional configuration needed. Broadcasting is automatic when:

1. Web app module is loaded
2. WebSocket endpoint is connected
3. Orchestrator has broadcast_callback available

## Monitoring

### Check Active WebSocket Connections

In dashboard backend:
```python
# In web app, check active connections
print(f"Active connections: {len(manager.active_connections)}")
```

### View Broadcast Messages

In browser console:
```javascript
// Messages logged to console
console.log(message);
```

## Performance Considerations

1. **Async Broadcasting**: Non-blocking, doesn't delay pipeline
2. **Connection Management**: Old connections auto-cleaned on send failure
3. **Message Rate**: One message per scored item (15-25/run typical)
4. **Payload Size**: ~200-500 bytes per message

## Troubleshooting

### WebSocket not connecting

```javascript
// Check in browser console
// Error: Failed to connect WebSocket

// Solutions:
// 1. Verify dashboard running on correct port
// 2. Check firewall/proxy settings
// 3. Check browser console for errors
```

### Messages not appearing

1. **Check dashboard is running**: `http://localhost:5000/health` should return 200
2. **Check WebSocket endpoint**: Connect to `/ws/progress/{profile_name}`
3. **Check orchestrator has callback**: Should log if broadcasting enabled
4. **Check CLI process**: Running in separate terminal

### Broadcast failures silently ignored

This is by design - orchestrator continues even if broadcasting fails. To troubleshoot:

```bash
# Run orchestrator with verbose logging
HORIZON_LOG_LEVEL=DEBUG python -m src.main --profile test
```

## Future Enhancements

### Phase 5 (Planned)
- [ ] Persist messages to database for replay
- [ ] Track broadcast latency
- [ ] Add message compression for large payloads
- [ ] Multiple consumer support (multiple dashboard instances)

### Phase 6 (Planned)
- [ ] Message filtering (show only certain sources)
- [ ] Message aggregation (batch sends)
- [ ] Real-time analytics dashboard
- [ ] Historical progress replay

## Known Limitations

1. **No Authentication**: WebSocket endpoint is open to all (add in Phase 5)
2. **Single Dashboard**: Messages sent to all connected clients
3. **No Message Persistence**: Messages lost if no clients connected
4. **Local Only**: Requires same-machine or network access

## API Reference

### ConnectionManager Methods

**broadcast(message: dict) -> Awaitable**:
- Sends message to all connected WebSocket clients
- Handles disconnections automatically
- Non-blocking, safe to call frequently

**connect(websocket: WebSocket) -> Awaitable**:
- Accept and register new WebSocket connection
- Called by FastAPI endpoint

**disconnect(websocket: WebSocket) -> None**:
- Remove WebSocket connection from active set
- Called on disconnect or error

### Message Types

| Type | Usage | Frequency |
|------|-------|-----------|
| `progress` | Scraping/analysis progress | 2-3 per run |
| `item_scored` | Individual article scored | 15-25 per run |
| `summary_complete` | Summary generation done | 1-2 per run |
| `ack` | Client keep-alive response | Variable |
| `error` | Error occurred | 0-1 per run |

---

**Status**: ✅ Phase 4B WebSocket Broadcasting Complete  
**Next**: Phase 4B Docker Updates + Phase 5 Production Deployment  
**Date**: May 5, 2026
