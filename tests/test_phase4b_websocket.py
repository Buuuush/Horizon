"""Tests for Phase 4B WebSocket broadcasting and Docker integration."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from src.orchestrator import HorizonOrchestrator
from src.models import Config, ContentItem, SourceType, Profile
from src.storage.manager import StorageManager


@pytest.fixture
def mock_config():
    """Create a mock configuration."""
    return MagicMock(spec=Config)


@pytest.fixture
def mock_storage():
    """Create a mock storage manager."""
    storage = MagicMock(spec=StorageManager)
    storage.get_active_profile.return_value = None
    return storage


@pytest.fixture
def mock_profile():
    """Create a mock profile."""
    profile = MagicMock(spec=Profile)
    profile.name = "test-profile"
    profile.ai_score_threshold = 7.0
    return profile


@pytest.fixture
async def broadcast_callback():
    """Create a mock broadcast callback."""
    callback = AsyncMock()
    return callback


class TestWebSocketBroadcasting:
    """Tests for WebSocket broadcasting functionality."""

    @pytest.mark.asyncio
    async def test_broadcast_callback_called(self, mock_config, mock_storage, mock_profile, broadcast_callback):
        """Test that broadcast callback is called when provided."""
        orchestrator = HorizonOrchestrator(
            mock_config,
            mock_storage,
            profile=mock_profile,
            broadcast_callback=broadcast_callback,
        )
        
        message = {
            "type": "progress",
            "stage": "scraping",
            "current": 10,
            "total": 10,
        }
        
        await orchestrator._broadcast(message)
        
        broadcast_callback.assert_called_once_with(message)

    @pytest.mark.asyncio
    async def test_broadcast_without_callback(self, mock_config, mock_storage, mock_profile):
        """Test that broadcasting works without callback (no-op)."""
        orchestrator = HorizonOrchestrator(
            mock_config,
            mock_storage,
            profile=mock_profile,
            broadcast_callback=None,
        )
        
        message = {"type": "progress", "stage": "scraping"}
        
        # Should not raise an exception
        await orchestrator._broadcast(message)

    @pytest.mark.asyncio
    async def test_broadcast_error_handling(self, mock_config, mock_storage, mock_profile):
        """Test that broadcast errors are handled gracefully."""
        failed_callback = AsyncMock(side_effect=Exception("Connection failed"))
        
        orchestrator = HorizonOrchestrator(
            mock_config,
            mock_storage,
            profile=mock_profile,
            broadcast_callback=failed_callback,
        )
        
        message = {"type": "progress", "stage": "scraping"}
        
        # Should not raise an exception despite callback failure
        await orchestrator._broadcast(message)
        failed_callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_callback_support(self, mock_config, mock_storage, mock_profile):
        """Test that sync callbacks are also supported."""
        sync_callback = MagicMock()
        
        orchestrator = HorizonOrchestrator(
            mock_config,
            mock_storage,
            profile=mock_profile,
            broadcast_callback=sync_callback,
        )
        
        message = {"type": "progress", "stage": "scraping"}
        
        await orchestrator._broadcast(message)
        
        sync_callback.assert_called_once_with(message)


class TestBroadcastMessageFormats:
    """Tests for proper message format."""

    @pytest.mark.asyncio
    async def test_progress_message_format(self, mock_config, mock_storage, mock_profile, broadcast_callback):
        """Test progress message has correct format."""
        orchestrator = HorizonOrchestrator(
            mock_config,
            mock_storage,
            profile=mock_profile,
            broadcast_callback=broadcast_callback,
        )
        
        await orchestrator._broadcast({
            "type": "progress",
            "stage": "scraping",
            "current": 42,
            "total": 42,
            "message": "Scraped 42 items",
        })
        
        call_args = broadcast_callback.call_args[0][0]
        assert call_args["type"] == "progress"
        assert call_args["stage"] == "scraping"
        assert call_args["current"] == 42
        assert call_args["total"] == 42

    @pytest.mark.asyncio
    async def test_item_scored_message_format(self, mock_config, mock_storage, mock_profile, broadcast_callback):
        """Test item_scored message has correct format."""
        orchestrator = HorizonOrchestrator(
            mock_config,
            mock_storage,
            profile=mock_profile,
            broadcast_callback=broadcast_callback,
        )
        
        await orchestrator._broadcast({
            "type": "item_scored",
            "item_id": "hn:12345",
            "title": "Test Article",
            "source": "hackernews",
            "score": 8.5,
            "url": "https://news.ycombinator.com/item?id=12345",
            "summary": "Test summary",
        })
        
        call_args = broadcast_callback.call_args[0][0]
        assert call_args["type"] == "item_scored"
        assert call_args["item_id"] == "hn:12345"
        assert call_args["score"] == 8.5
        assert "title" in call_args
        assert "source" in call_args

    @pytest.mark.asyncio
    async def test_summary_complete_message_format(self, mock_config, mock_storage, mock_profile, broadcast_callback):
        """Test summary_complete message has correct format."""
        orchestrator = HorizonOrchestrator(
            mock_config,
            mock_storage,
            profile=mock_profile,
            broadcast_callback=broadcast_callback,
        )
        
        await orchestrator._broadcast({
            "type": "summary_complete",
            "profile_name": "test-profile",
            "language": "bilingual",
            "path": "/app/data/summaries/2026-05-05-summary.html",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "items_count": 15,
        })
        
        call_args = broadcast_callback.call_args[0][0]
        assert call_args["type"] == "summary_complete"
        assert call_args["profile_name"] == "test-profile"
        assert call_args["language"] == "bilingual"
        assert "path" in call_args
        assert "timestamp" in call_args
        assert call_args["items_count"] == 15


class TestOrchestratorWithBroadcasting:
    """Integration tests for orchestrator with broadcasting."""

    @pytest.mark.asyncio
    async def test_orchestrator_initialization_with_callback(self, mock_config, mock_storage, mock_profile, broadcast_callback):
        """Test orchestrator initializes with broadcast callback."""
        orchestrator = HorizonOrchestrator(
            mock_config,
            mock_storage,
            profile=mock_profile,
            broadcast_callback=broadcast_callback,
        )
        
        assert orchestrator.broadcast_callback == broadcast_callback
        assert orchestrator.profile == mock_profile

    @pytest.mark.asyncio
    async def test_profile_threshold_used_in_broadcast(self, mock_config, mock_storage, mock_profile, broadcast_callback):
        """Test that profile threshold is available for broadcasting decisions."""
        mock_profile.ai_score_threshold = 8.5
        
        orchestrator = HorizonOrchestrator(
            mock_config,
            mock_storage,
            profile=mock_profile,
            broadcast_callback=broadcast_callback,
        )
        
        assert orchestrator.profile.ai_score_threshold == 8.5
        
        # Simulate broadcasting an item that would be filtered
        await orchestrator._broadcast({
            "type": "item_scored",
            "score": 7.0,  # Below threshold
            "title": "Low score article",
        })
        
        broadcast_callback.assert_called()


class TestConnectionManager:
    """Tests for WebSocket ConnectionManager."""

    def test_connection_manager_initialization(self):
        """Test ConnectionManager initializes with empty connections."""
        from src.web.app import ConnectionManager
        
        manager = ConnectionManager()
        assert len(manager.active_connections) == 0

    @pytest.mark.asyncio
    async def test_connection_manager_broadcast(self):
        """Test ConnectionManager broadcasts to connected clients."""
        from src.web.app import ConnectionManager
        
        manager = ConnectionManager()
        
        # Create mock WebSocket
        mock_ws = AsyncMock()
        manager.active_connections.add(mock_ws)
        
        message = {"type": "test", "data": "test"}
        await manager.broadcast(message)
        
        mock_ws.send_json.assert_called_once_with(message)

    @pytest.mark.asyncio
    async def test_connection_manager_cleanup_on_error(self):
        """Test ConnectionManager removes failed connections."""
        from src.web.app import ConnectionManager
        
        manager = ConnectionManager()
        
        # Create mock WebSocket that fails
        failed_ws = AsyncMock(side_effect=Exception("Send failed"))
        working_ws = AsyncMock()
        
        manager.active_connections.add(failed_ws)
        manager.active_connections.add(working_ws)
        
        message = {"type": "test"}
        await manager.broadcast(message)
        
        # Failed connection should be removed
        assert failed_ws not in manager.active_connections
        # Working connection should still be there
        assert working_ws in manager.active_connections

    @pytest.mark.asyncio
    async def test_connection_connect_disconnect(self):
        """Test connection and disconnection."""
        from src.web.app import ConnectionManager
        
        manager = ConnectionManager()
        mock_ws = AsyncMock()
        
        # Connect
        await manager.connect(mock_ws)
        mock_ws.accept.assert_called_once()
        assert mock_ws in manager.active_connections
        
        # Disconnect
        manager.disconnect(mock_ws)
        assert mock_ws not in manager.active_connections


class TestDockerIntegration:
    """Tests for Docker deployment integration."""

    def test_docker_compose_file_exists(self):
        """Test docker-compose.yml exists and is valid."""
        import yaml
        from pathlib import Path
        
        compose_file = Path("docker-compose.yml")
        assert compose_file.exists(), "docker-compose.yml not found"
        
        with open(compose_file) as f:
            config = yaml.safe_load(f)
        
        assert "services" in config
        assert "dashboard" in config["services"]
        assert "orchestrator" in config["services"]

    def test_dockerfile_exists(self):
        """Test Dockerfile exists."""
        from pathlib import Path
        
        dockerfile = Path("Dockerfile")
        assert dockerfile.exists(), "Dockerfile not found"
        
        with open(dockerfile) as f:
            content = f.read()
        
        # Check for key Docker directives
        assert "FROM python" in content
        assert "EXPOSE 5000" in content
        assert "VOLUME" in content

    def test_docker_compose_dashboard_config(self):
        """Test docker-compose dashboard service configuration."""
        import yaml
        from pathlib import Path
        
        with open("docker-compose.yml") as f:
            config = yaml.safe_load(f)
        
        dashboard = config["services"]["dashboard"]
        
        # Check essential config
        assert dashboard["ports"] == ["5000:5000"]
        assert dashboard["container_name"] == "horizon-dashboard"
        assert "healthcheck" in dashboard
        assert "uvicorn" in dashboard["command"][3]

    def test_docker_compose_orchestrator_config(self):
        """Test docker-compose orchestrator service configuration."""
        import yaml
        from pathlib import Path
        
        with open("docker-compose.yml") as f:
            config = yaml.safe_load(f)
        
        orchestrator = config["services"]["orchestrator"]
        
        # Check essential config
        assert orchestrator["container_name"] == "horizon-orchestrator"
        assert "depends_on" in orchestrator
        assert orchestrator["depends_on"]["dashboard"]["condition"] == "service_healthy"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
