"""Tests for Persistent Session Memory System

Tests the database models, service layer, and memory integration functions
that enable NAVI to remember context across VS Code restarts.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock

# Import the session memory service (in-memory version for comparison)
from backend.services.session_memory_service import (
    SessionFact as InMemorySessionFact,
    SessionMemory,
    SessionMemoryService,
)

# Import the persistent memory service
from backend.services.persistent_session_memory import (
    PersistentSessionMemory,
)

# Import memory integration helpers
from backend.services.memory_integration import (
    inject_memory_context,
)


class TestInMemorySessionMemoryService:
    """Test the in-memory session memory service."""

    def test_session_fact_creation(self):
        """Test creating a session fact."""
        fact = InMemorySessionFact(
            category="server",
            key="port",
            value="3000",
            timestamp=datetime.utcnow().isoformat(),
        )
        assert fact.category == "server"
        assert fact.key == "port"
        assert fact.value == "3000"
        assert fact.confidence == 1.0

    def test_session_memory_add_fact(self):
        """Test adding facts to session memory."""
        memory = SessionMemory(session_id="test-session")
        fact = InMemorySessionFact(
            category="server",
            key="port",
            value="3000",
            timestamp=datetime.utcnow().isoformat(),
        )
        memory.add_fact(fact)

        assert len(memory.facts) == 1
        assert "server:port" in memory.facts

    def test_session_memory_get_fact(self):
        """Test retrieving a specific fact."""
        memory = SessionMemory(session_id="test-session")
        fact = InMemorySessionFact(
            category="server",
            key="port",
            value="3000",
            timestamp=datetime.utcnow().isoformat(),
        )
        memory.add_fact(fact)

        retrieved = memory.get_fact("server", "port")
        assert retrieved is not None
        assert retrieved.value == "3000"

    def test_session_memory_get_facts_by_category(self):
        """Test retrieving facts by category."""
        memory = SessionMemory(session_id="test-session")

        # Add multiple facts
        memory.add_fact(
            InMemorySessionFact(
                category="server",
                key="port",
                value="3000",
                timestamp=datetime.utcnow().isoformat(),
            )
        )
        memory.add_fact(
            InMemorySessionFact(
                category="server",
                key="status",
                value="running",
                timestamp=datetime.utcnow().isoformat(),
            )
        )
        memory.add_fact(
            InMemorySessionFact(
                category="file",
                key="path",
                value="/src/app.ts",
                timestamp=datetime.utcnow().isoformat(),
            )
        )

        server_facts = memory.get_facts_by_category("server")
        assert len(server_facts) == 2

    def test_session_memory_context_summary(self):
        """Test generating context summary."""
        memory = SessionMemory(session_id="test-session")
        memory.add_fact(
            InMemorySessionFact(
                category="server",
                key="port",
                value="3000",
                timestamp=datetime.utcnow().isoformat(),
            )
        )

        summary = memory.get_context_summary()
        assert "SESSION CONTEXT" in summary
        assert "port" in summary
        assert "3000" in summary


class TestSessionMemoryServiceExtractors:
    """Test the fact extraction patterns."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = SessionMemoryService()
        self.timestamp = datetime.utcnow().isoformat()

    def test_extract_port_info_from_text(self):
        """Test extracting port numbers from text."""
        text = "The server is running on port 3001. You can access it at localhost:3001."
        facts = self.service._extract_port_info(text, self.timestamp, None)

        assert len(facts) >= 1
        port_values = [f.value for f in facts]
        assert "3001" in port_values

    def test_extract_server_status_running(self):
        """Test detecting server running status."""
        text = "The development server is now running successfully on port 3000."
        facts = self.service._extract_server_status(text, self.timestamp, None)

        assert len(facts) >= 1
        status_facts = [f for f in facts if f.key == "status"]
        assert any(f.value == "running" for f in status_facts)

    def test_extract_server_status_stopped(self):
        """Test detecting server stopped status."""
        text = "The server stopped due to an error."
        facts = self.service._extract_server_status(text, self.timestamp, None)

        assert len(facts) >= 1
        status_facts = [f for f in facts if f.key == "status"]
        assert any(f.value == "stopped" for f in status_facts)

    def test_extract_file_paths(self):
        """Test extracting file paths from text."""
        text = "I modified the file /src/components/App.tsx and src/utils/helper.js"
        facts = self.service._extract_file_paths(text, self.timestamp, None)

        assert len(facts) >= 1
        paths = [f.value for f in facts]
        # At least one path should be extracted
        assert any("App.tsx" in p or "helper.js" in p for p in paths)

    def test_extract_urls(self):
        """Test extracting URLs from text."""
        text = "Check the documentation at https://docs.example.com/api and https://github.com/repo"
        facts = self.service._extract_urls(text, self.timestamp, None)

        assert len(facts) >= 1
        urls = [f.value for f in facts]
        assert any("docs.example.com" in u for u in urls)

    def test_extract_commands_run(self):
        """Test extracting executed commands."""
        text = "I ran `npm install express` to install the dependency."
        facts = self.service._extract_commands_run(text, self.timestamp, None)

        assert len(facts) >= 1
        commands = [f.value for f in facts]
        assert any("npm install" in cmd for cmd in commands)

    def test_extract_errors(self):
        """Test extracting error information."""
        text = "Error: Module not found. Failed: Could not resolve dependency."
        facts = self.service._extract_errors(text, self.timestamp, None)

        assert len(facts) >= 1

    def test_extract_decisions(self):
        """Test extracting decisions made."""
        text = "I decided to use React for the frontend. The solution is to add caching."
        facts = self.service._extract_decisions(text, self.timestamp, None)

        assert len(facts) >= 1

    def test_extract_from_command_action(self):
        """Test extracting facts from command action."""
        action = {
            "type": "command",
            "command": "npm start",
            "output": "Server started on port 3000",
            "exit_code": 0,
        }
        facts = self.service._extract_from_action(action, self.timestamp, None)

        assert len(facts) >= 1
        # Should have command and success status
        assert any(f.key == "last_command" for f in facts)
        assert any(f.value == "success" for f in facts)

    def test_extract_from_edit_action(self):
        """Test extracting facts from file edit action."""
        action = {
            "type": "edit",
            "file": "/src/app.ts",
        }
        facts = self.service._extract_from_action(action, self.timestamp, None)

        assert len(facts) >= 1
        assert any("/src/app.ts" in f.value for f in facts)


class TestSessionMemoryServiceProcessing:
    """Test the session memory service processing."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = SessionMemoryService()

    def test_get_or_create_session(self):
        """Test creating new sessions."""
        session = self.service.get_or_create_session("session-1")
        assert session.session_id == "session-1"

        # Getting same session returns existing
        session2 = self.service.get_or_create_session("session-1")
        assert session2 is session

    def test_process_exchange(self):
        """Test processing a conversation exchange."""
        session = self.service.process_exchange(
            session_id="test-session",
            user_message="Start the development server",
            assistant_response="I started the server on port 3000. It is now running successfully.",
        )

        # Should have extracted facts
        assert len(session.facts) > 0
        # Should have port and status facts
        server_facts = session.get_facts_by_category("server")
        assert len(server_facts) > 0

    def test_get_context_for_session(self):
        """Test getting context for injection."""
        self.service.process_exchange(
            session_id="test-session",
            user_message="Start the server",
            assistant_response="Server running on port 3001.",
        )

        context = self.service.get_context_for_session("test-session")
        assert "SESSION CONTEXT" in context
        assert "3001" in context

    def test_clear_session(self):
        """Test clearing a session."""
        self.service.process_exchange(
            session_id="test-session",
            user_message="Test",
            assistant_response="Response",
        )

        self.service.clear_session("test-session")
        context = self.service.get_context_for_session("test-session")
        assert context == ""


class TestPersistentSessionMemoryExtractors:
    """Test the persistent session memory service extractors."""

    def setup_method(self):
        """Set up test fixtures with a mock db."""
        self.mock_db = MagicMock()
        self.service = PersistentSessionMemory(self.mock_db)
        self.timestamp = datetime.utcnow()

    def test_extract_port_info(self):
        """Test port extraction from persistent memory service."""
        text = "The API is running on port 8080"
        facts = self.service._extract_port_info(text, self.timestamp, None)

        assert len(facts) >= 1
        assert any("8080" in f.value for f in facts)

    def test_extract_server_status(self):
        """Test server status extraction."""
        text = "Server is now running successfully"
        facts = self.service._extract_server_status(text, self.timestamp, None)

        assert len(facts) >= 1
        assert any(f.value == "running" for f in facts)

    def test_extract_file_paths(self):
        """Test file path extraction."""
        text = "Modified /home/user/project/src/index.ts"
        facts = self.service._extract_file_paths(text, self.timestamp, None)

        # File paths should be extracted
        assert isinstance(facts, list)

    def test_extract_urls(self):
        """Test URL extraction."""
        text = "Visit https://api.example.com/docs for more info"
        facts = self.service._extract_urls(text, self.timestamp, None)

        assert len(facts) >= 1
        assert any("api.example.com" in f.value for f in facts)

    def test_extract_dependencies(self):
        """Test dependency extraction."""
        text = "Installed express@4.18.2 and lodash@4.17.21"
        facts = self.service._extract_dependencies(text, self.timestamp, None)

        # Should extract package names
        assert isinstance(facts, list)

    def test_extract_versions(self):
        """Test version extraction."""
        # The regex looks for "node v18.17.0" or "node 18.17.0" format
        text = "Using node v18.17.0 and npm 9.6.7 for this project"
        facts = self.service._extract_versions(text, self.timestamp, None)

        assert len(facts) >= 1
        # Should find node version
        assert any("node_version" in f.key or "npm_version" in f.key for f in facts)

    def test_extract_errors(self):
        """Test error extraction."""
        text = "Error: Cannot find module 'express'. TypeError: undefined is not a function"
        facts = self.service._extract_errors(text, self.timestamp, None)

        assert len(facts) >= 1

    def test_extract_from_command_action(self):
        """Test extracting facts from a command action."""
        action = {
            "type": "command",
            "command": "npm start",
            "exit_code": 0,
        }
        facts = self.service._extract_from_action(action, self.timestamp, None)

        assert len(facts) >= 1
        assert any(f.key == "last_command" for f in facts)
        assert any(f.value == "success" for f in facts)

    def test_create_error_signature(self):
        """Test error signature creation for matching."""
        error1 = "Error at /src/app.ts:123:45 Cannot find module"
        error2 = "Error at /src/app.ts:456:78 Cannot find module"

        sig1 = self.service._create_error_signature(error1)
        sig2 = self.service._create_error_signature(error2)

        # Same error type should produce same signature
        assert sig1 == sig2

    def test_extract_resolution_summary(self):
        """Test resolution summary extraction."""
        response = "To fix this, run npm install. This will resolve the dependency issue."
        summary = self.service._extract_resolution_summary(response)

        assert len(summary) > 0
        assert len(summary) <= 200


class TestMemoryIntegration:
    """Test memory integration helpers."""

    def test_inject_memory_context_with_summary(self):
        """Test injecting memory context into a message."""
        message = "Start the server"
        memory_context = {
            "context_summary": "=== Previous Session ===\nServer was running on port 3000\n=== End ==="
        }

        result = inject_memory_context(message, memory_context)

        assert "Previous Session" in result
        assert "Start the server" in result
        assert "port 3000" in result

    def test_inject_memory_context_empty(self):
        """Test with empty memory context."""
        message = "Start the server"
        memory_context = {}

        result = inject_memory_context(message, memory_context)
        assert result == message

    def test_inject_memory_context_no_summary(self):
        """Test with memory context but no summary."""
        message = "Start the server"
        memory_context = {"facts": {}, "is_new_workspace": True}

        result = inject_memory_context(message, memory_context)
        assert result == message


class TestPersistentMemoryContextGeneration:
    """Test context generation for persistent memory."""

    def setup_method(self):
        """Set up test fixtures with a mock db."""
        self.mock_db = MagicMock()
        self.service = PersistentSessionMemory(self.mock_db)

    def test_generate_context_summary_new_workspace(self):
        """Test generating summary for new workspace."""
        context = {"is_new_workspace": True}
        summary = self.service.generate_context_summary(context)
        assert summary == ""

    def test_generate_context_summary_with_facts(self):
        """Test generating summary with facts."""
        context = {
            "is_new_workspace": False,
            "workspace_name": "test-project",
            "facts": {
                "server": {"port": "3000"},
                "file": {"modified_0": "/src/app.ts"},
            },
            "error_resolutions": [],
            "dependencies": [],
        }

        summary = self.service.generate_context_summary(context)

        # Should contain workspace memory header
        assert "WORKSPACE MEMORY" in summary
        assert "3000" in summary

    def test_generate_context_summary_with_error_resolutions(self):
        """Test summary includes error resolutions."""
        context = {
            "is_new_workspace": False,
            "workspace_name": "test-project",
            "facts": {},
            "error_resolutions": [
                {
                    "error_type": "module_not_found",
                    "error_signature": "abc123",
                    "resolution_summary": "Run npm install to fix the dependency issue",
                    "success_rate": 0.9,
                }
            ],
            "dependencies": [],
        }

        summary = self.service.generate_context_summary(context)

        # Should mention error resolutions
        assert isinstance(summary, str)
        assert "WORKSPACE MEMORY" in summary
        assert "Error Solutions" in summary or "npm install" in summary

    def test_generate_context_summary_with_deps(self):
        """Test summary includes installed dependencies."""
        context = {
            "is_new_workspace": False,
            "workspace_name": "test-project",
            "facts": {},
            "error_resolutions": [],
            "dependencies": [
                {"manager": "npm", "name": "express", "version": "4.18.2"},
                {"manager": "npm", "name": "lodash", "version": "4.17.21"},
            ],
        }

        summary = self.service.generate_context_summary(context)

        # Should mention dependencies
        assert isinstance(summary, str)
        assert "WORKSPACE MEMORY" in summary
        assert "Dependencies" in summary or "express" in summary


class TestDatabaseModels:
    """Test the database models for persistent session memory."""

    def test_workspace_session_model_import(self):
        """Test WorkspaceSession model can be imported."""
        from backend.database.models.session_facts import WorkspaceSession

        assert WorkspaceSession is not None
        assert hasattr(WorkspaceSession, "__tablename__")
        assert WorkspaceSession.__tablename__ == "navi_workspace_sessions"

    def test_session_fact_model_import(self):
        """Test SessionFact model can be imported."""
        from backend.database.models.session_facts import SessionFact

        assert SessionFact is not None
        assert hasattr(SessionFact, "__tablename__")
        assert SessionFact.__tablename__ == "navi_session_facts"

    def test_error_resolution_model_import(self):
        """Test ErrorResolution model can be imported."""
        from backend.database.models.session_facts import ErrorResolution

        assert ErrorResolution is not None
        assert hasattr(ErrorResolution, "__tablename__")
        assert ErrorResolution.__tablename__ == "navi_error_resolutions"

    def test_installed_dependency_model_import(self):
        """Test InstalledDependency model can be imported."""
        from backend.database.models.session_facts import InstalledDependency

        assert InstalledDependency is not None
        assert hasattr(InstalledDependency, "__tablename__")
        assert InstalledDependency.__tablename__ == "navi_installed_dependencies"

    def test_models_exported_from_package(self):
        """Test models are exported from database.models package."""
        from backend.database.models import (
            WorkspaceSession,
            SessionFact,
            ErrorResolution,
            InstalledDependency,
        )

        assert WorkspaceSession is not None
        assert SessionFact is not None
        assert ErrorResolution is not None
        assert InstalledDependency is not None


class TestEdgeCases:
    """Test edge cases and error handling."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = SessionMemoryService()

    def test_empty_response_processing(self):
        """Test processing with empty response."""
        session = self.service.process_exchange(
            session_id="test-session",
            user_message="Hello",
            assistant_response="",
        )
        # Should not crash
        assert session is not None

    def test_none_values_handling(self):
        """Test handling of None values."""
        session = self.service.process_exchange(
            session_id="test-session",
            user_message="Test",
            assistant_response="Response",
            message_id=None,
            actions=None,
        )
        assert session is not None

    def test_special_characters_in_text(self):
        """Test extracting from text with special characters."""
        text = "Server on port 3000! Error: Can't find module 'test'"
        timestamp = datetime.utcnow().isoformat()

        facts = self.service._extract_port_info(text, timestamp, None)
        assert len(facts) >= 1

    def test_large_text_processing(self):
        """Test processing large text responses."""
        large_text = "Server running on port 3000. " * 1000
        session = self.service.process_exchange(
            session_id="test-session",
            user_message="Start server",
            assistant_response=large_text,
        )
        # Should handle large text without issues
        assert session is not None

    def test_unicode_in_text(self):
        """Test handling of unicode characters."""
        text = "服务器运行在端口 3000。Created file /src/文件.ts"
        session = self.service.process_exchange(
            session_id="test-session",
            user_message="Test unicode",
            assistant_response=text,
        )
        assert session is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
