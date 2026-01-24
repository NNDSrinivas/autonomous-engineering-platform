"""
Codebase Memory Service for NAVI.

Manages codebase indexing, symbol extraction, and pattern detection
for code-aware AI responses.

Features:
- Workspace scanning and indexing
- Code symbol extraction (functions, classes, etc.)
- Code embedding for semantic search
- Pattern detection in codebase
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session

from backend.database.models.memory import (
    CodebaseIndex,
    CodePattern,
    CodeSymbol,
)
from backend.services.memory.embedding_service import get_embedding_service

logger = logging.getLogger(__name__)

# File extensions by language
LANGUAGE_EXTENSIONS = {
    "python": [".py", ".pyi"],
    "javascript": [".js", ".mjs", ".cjs"],
    "typescript": [".ts", ".tsx", ".mts", ".cts"],
    "java": [".java"],
    "go": [".go"],
    "rust": [".rs"],
    "c": [".c", ".h"],
    "cpp": [".cpp", ".cc", ".cxx", ".hpp", ".hh"],
    "csharp": [".cs"],
    "ruby": [".rb"],
    "php": [".php"],
    "swift": [".swift"],
    "kotlin": [".kt", ".kts"],
    "scala": [".scala"],
    "sql": [".sql"],
    "shell": [".sh", ".bash", ".zsh"],
}

# Directories to ignore during indexing
IGNORE_DIRS = {
    ".git",
    ".svn",
    ".hg",
    "node_modules",
    "vendor",
    "venv",
    ".venv",
    "env",
    ".env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "dist",
    "build",
    "target",
    "out",
    ".idea",
    ".vscode",
    ".vs",
    "coverage",
    ".coverage",
}

# Files to ignore
IGNORE_FILES = {
    ".DS_Store",
    "Thumbs.db",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "Pipfile.lock",
}


class CodebaseMemoryService:
    """
    Service for managing codebase memory.

    Provides methods to index codebases, extract symbols,
    detect patterns, and search code semantically.
    """

    def __init__(self, db: Session):
        """
        Initialize the codebase memory service.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.embedding_service = get_embedding_service()

    # =========================================================================
    # Codebase Index Management
    # =========================================================================

    def create_index(
        self,
        workspace_path: str,
        user_id: Optional[int] = None,
        org_id: Optional[int] = None,
        workspace_name: Optional[str] = None,
        index_config: Optional[Dict[str, Any]] = None,
    ) -> CodebaseIndex:
        """
        Create a new codebase index.

        Args:
            workspace_path: Path to the workspace
            user_id: Optional owner user ID
            org_id: Optional organization ID
            workspace_name: Optional friendly name
            index_config: Optional indexing configuration

        Returns:
            Created CodebaseIndex
        """
        # Check for existing index
        existing = self.get_index_by_path(workspace_path, user_id)
        if existing:
            return existing

        # Derive workspace name if not provided
        if not workspace_name:
            workspace_name = Path(workspace_path).name

        index = CodebaseIndex(
            workspace_path=workspace_path,
            user_id=user_id,
            org_id=org_id,
            workspace_name=workspace_name,
            index_config=index_config or {},
            index_status="pending",
        )
        self.db.add(index)
        self.db.commit()
        self.db.refresh(index)

        logger.info(f"Created codebase index {index.id} for {workspace_path}")
        return index

    def get_index(self, index_id: UUID) -> Optional[CodebaseIndex]:
        """
        Get a codebase index by ID.

        Args:
            index_id: Index ID

        Returns:
            CodebaseIndex or None if not found
        """
        return self.db.query(CodebaseIndex).filter(CodebaseIndex.id == index_id).first()

    def get_index_by_path(
        self,
        workspace_path: str,
        user_id: Optional[int] = None,
    ) -> Optional[CodebaseIndex]:
        """
        Get a codebase index by workspace path.

        Args:
            workspace_path: Path to the workspace
            user_id: Optional user ID filter

        Returns:
            CodebaseIndex or None if not found
        """
        query = self.db.query(CodebaseIndex).filter(
            CodebaseIndex.workspace_path == workspace_path
        )

        if user_id is not None:
            query = query.filter(CodebaseIndex.user_id == user_id)

        return query.first()

    def get_user_indexes(
        self,
        user_id: int,
        limit: int = 50,
    ) -> List[CodebaseIndex]:
        """
        Get all codebase indexes for a user.

        Args:
            user_id: User ID
            limit: Maximum indexes to return

        Returns:
            List of CodebaseIndex objects
        """
        return (
            self.db.query(CodebaseIndex)
            .filter(CodebaseIndex.user_id == user_id)
            .order_by(desc(CodebaseIndex.updated_at))
            .limit(limit)
            .all()
        )

    def update_index_status(
        self,
        index_id: UUID,
        status: str,
        error: Optional[str] = None,
        file_count: Optional[int] = None,
        symbol_count: Optional[int] = None,
        total_lines: Optional[int] = None,
    ) -> Optional[CodebaseIndex]:
        """
        Update codebase index status.

        Args:
            index_id: Index ID
            status: New status
            error: Optional error message
            file_count: Optional file count
            symbol_count: Optional symbol count
            total_lines: Optional total lines

        Returns:
            Updated CodebaseIndex or None
        """
        index = self.get_index(index_id)
        if not index:
            return None

        index.index_status = status
        index.last_error = error

        if status == "ready":
            index.last_indexed = datetime.utcnow()

        if file_count is not None:
            index.file_count = file_count
        if symbol_count is not None:
            index.symbol_count = symbol_count
        if total_lines is not None:
            index.total_lines = total_lines

        self.db.commit()
        self.db.refresh(index)
        return index

    def delete_index(self, index_id: UUID) -> bool:
        """
        Delete a codebase index and all related data.

        Args:
            index_id: Index ID

        Returns:
            True if deleted, False if not found
        """
        result = (
            self.db.query(CodebaseIndex).filter(CodebaseIndex.id == index_id).delete()
        )
        self.db.commit()
        return result > 0

    # =========================================================================
    # File Scanning
    # =========================================================================

    def scan_workspace(
        self,
        workspace_path: str,
        include_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Scan a workspace for indexable files.

        Args:
            workspace_path: Path to the workspace
            include_patterns: Optional glob patterns to include
            exclude_patterns: Optional glob patterns to exclude

        Returns:
            List of file information dicts
        """
        workspace = Path(workspace_path)
        if not workspace.exists():
            logger.error(f"Workspace not found: {workspace_path}")
            return []

        files = []
        all_extensions = set()
        for exts in LANGUAGE_EXTENSIONS.values():
            all_extensions.update(exts)

        for root, dirs, filenames in os.walk(workspace):
            # Skip ignored directories
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

            for filename in filenames:
                # Skip ignored files
                if filename in IGNORE_FILES:
                    continue

                file_path = Path(root) / filename
                extension = file_path.suffix.lower()

                # Check if it's a supported file type
                if extension not in all_extensions:
                    continue

                # Determine language
                language = None
                for lang, exts in LANGUAGE_EXTENSIONS.items():
                    if extension in exts:
                        language = lang
                        break

                if language:
                    try:
                        stat = file_path.stat()
                        files.append(
                            {
                                "path": str(file_path),
                                "relative_path": str(file_path.relative_to(workspace)),
                                "language": language,
                                "size": stat.st_size,
                                "modified": datetime.fromtimestamp(stat.st_mtime),
                            }
                        )
                    except OSError as e:
                        logger.warning(f"Failed to stat file {file_path}: {e}")

        return files

    def _detect_language(self, file_path: str) -> Optional[str]:
        """Detect programming language from file extension."""
        extension = Path(file_path).suffix.lower()
        for lang, exts in LANGUAGE_EXTENSIONS.items():
            if extension in exts:
                return lang
        return None

    # =========================================================================
    # Symbol Extraction
    # =========================================================================

    async def add_symbol(
        self,
        codebase_id: UUID,
        symbol_type: str,
        symbol_name: str,
        file_path: str,
        line_start: int,
        line_end: int,
        language: str,
        code_snippet: Optional[str] = None,
        signature: Optional[str] = None,
        documentation: Optional[str] = None,
        qualified_name: Optional[str] = None,
        parent_symbol_id: Optional[UUID] = None,
        generate_embedding: bool = True,
    ) -> CodeSymbol:
        """
        Add a code symbol to the index.

        Args:
            codebase_id: Codebase index ID
            symbol_type: Type of symbol (function, class, etc.)
            symbol_name: Symbol name
            file_path: File path containing the symbol
            line_start: Starting line number
            line_end: Ending line number
            language: Programming language
            code_snippet: Optional code snippet
            signature: Optional function/method signature
            documentation: Optional docstring
            qualified_name: Optional fully qualified name
            parent_symbol_id: Optional parent symbol ID
            generate_embedding: Whether to generate embedding

        Returns:
            Created CodeSymbol
        """
        embedding_text = None
        if generate_embedding and (code_snippet or signature or documentation):
            # Build text for embedding
            embed_parts = [f"Symbol: {symbol_name}", f"Type: {symbol_type}"]
            if signature:
                embed_parts.append(f"Signature: {signature}")
            if documentation:
                embed_parts.append(f"Documentation: {documentation}")
            if code_snippet:
                embed_parts.append(f"Code:\n{code_snippet[:1000]}")

            embed_text = "\n".join(embed_parts)
            embedding_text = await self.embedding_service.embed_code(
                embed_text, language or "unknown", context=qualified_name
            )

        symbol = CodeSymbol(
            codebase_id=codebase_id,
            symbol_type=symbol_type,
            symbol_name=symbol_name,
            qualified_name=qualified_name,
            file_path=file_path,
            line_start=line_start,
            line_end=line_end,
            code_snippet=code_snippet,
            documentation=documentation,
            embedding_text=embedding_text,
            parent_symbol_id=parent_symbol_id,
        )
        self.db.add(symbol)
        self.db.commit()
        self.db.refresh(symbol)
        return symbol

    # Alias for backward compatibility
    async def index_symbol(self, *args, **kwargs) -> CodeSymbol:
        """Alias for add_symbol."""
        return await self.add_symbol(*args, **kwargs)

    def get_symbols(
        self,
        codebase_id: UUID,
        symbol_type: Optional[str] = None,
        file_path: Optional[str] = None,
        limit: int = 100,
    ) -> List[CodeSymbol]:
        """
        Get code symbols from an index.

        Args:
            codebase_id: Codebase index ID
            symbol_type: Optional filter by symbol type
            file_path: Optional filter by file path
            limit: Maximum symbols to return

        Returns:
            List of CodeSymbol objects
        """
        query = self.db.query(CodeSymbol).filter(CodeSymbol.codebase_id == codebase_id)

        if symbol_type:
            query = query.filter(CodeSymbol.symbol_type == symbol_type)

        if file_path:
            query = query.filter(CodeSymbol.file_path == file_path)

        return (
            query.order_by(CodeSymbol.file_path, CodeSymbol.line_start)
            .limit(limit)
            .all()
        )

    def find_symbol_by_name(
        self,
        codebase_id: UUID,
        name: str,
        exact: bool = False,
    ) -> List[CodeSymbol]:
        """
        Find symbols by name.

        Args:
            codebase_id: Codebase index ID
            name: Symbol name to search
            exact: Whether to match exactly

        Returns:
            List of matching CodeSymbol objects
        """
        query = self.db.query(CodeSymbol).filter(CodeSymbol.codebase_id == codebase_id)

        if exact:
            query = query.filter(CodeSymbol.symbol_name == name)
        else:
            query = query.filter(CodeSymbol.symbol_name.ilike(f"%{name}%"))

        return query.limit(50).all()

    async def search_symbols(
        self,
        codebase_id: UUID,
        query: str,
        symbol_type: Optional[str] = None,
        limit: int = 10,
        min_similarity: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """
        Semantic search for code symbols.

        Args:
            codebase_id: Codebase index ID
            query: Search query
            symbol_type: Optional filter by symbol type
            limit: Maximum results
            min_similarity: Minimum similarity threshold

        Returns:
            List of matching symbols with scores
        """
        # Generate query embedding
        query_embedding = await self.embedding_service.embed_text(query)

        # Get symbols with embeddings
        db_query = self.db.query(CodeSymbol).filter(
            and_(
                CodeSymbol.codebase_id == codebase_id,
                CodeSymbol.embedding_text.isnot(None),
            )
        )

        if symbol_type:
            db_query = db_query.filter(CodeSymbol.symbol_type == symbol_type)

        symbols = db_query.all()

        # Calculate similarities
        results = []
        for symbol in symbols:
            if symbol.embedding_text is None:
                continue

            symbol_embedding = list(symbol.embedding_text)
            similarity = self.embedding_service.cosine_similarity(
                query_embedding, symbol_embedding
            )

            if similarity >= min_similarity:
                results.append(
                    {
                        "id": str(symbol.id),
                        "name": symbol.symbol_name,
                        "qualified_name": symbol.qualified_name,
                        "type": symbol.symbol_type,
                        "file_path": symbol.file_path,
                        "line_start": symbol.line_start,
                        "line_end": symbol.line_end,
                        "documentation": symbol.documentation,
                        "similarity": similarity,
                    }
                )

        # Sort by similarity
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:limit]

    def clear_symbols(self, codebase_id: UUID) -> int:
        """
        Clear all symbols for a codebase index.

        Args:
            codebase_id: Codebase index ID

        Returns:
            Number of symbols deleted
        """
        result = (
            self.db.query(CodeSymbol)
            .filter(CodeSymbol.codebase_id == codebase_id)
            .delete()
        )
        self.db.commit()
        return result

    # =========================================================================
    # Pattern Detection
    # =========================================================================

    def add_pattern(
        self,
        codebase_id: UUID,
        pattern_type: str,
        pattern_name: str,
        description: Optional[str] = None,
        examples: Optional[List[Dict[str, Any]]] = None,
        confidence: float = 0.5,
        occurrences: int = 1,
    ) -> CodePattern:
        """
        Add a detected code pattern.

        Args:
            codebase_id: Codebase index ID
            pattern_type: Type of pattern
            pattern_name: Pattern name
            description: Optional description
            examples: Optional code examples
            confidence: Confidence level
            occurrences: Number of occurrences

        Returns:
            Created CodePattern
        """
        pattern = CodePattern(
            codebase_id=codebase_id,
            pattern_type=pattern_type,
            pattern_name=pattern_name,
            description=description,
            examples=examples or [],
            confidence=confidence,
            occurrences=occurrences,
        )
        self.db.add(pattern)
        self.db.commit()
        self.db.refresh(pattern)
        return pattern

    def get_patterns(
        self,
        codebase_id: UUID,
        pattern_type: Optional[str] = None,
        min_confidence: float = 0.0,
    ) -> List[CodePattern]:
        """
        Get detected code patterns.

        Args:
            codebase_id: Codebase index ID
            pattern_type: Optional filter by type
            min_confidence: Minimum confidence threshold

        Returns:
            List of CodePattern objects
        """
        query = self.db.query(CodePattern).filter(
            and_(
                CodePattern.codebase_id == codebase_id,
                CodePattern.confidence >= min_confidence,
            )
        )

        if pattern_type:
            query = query.filter(CodePattern.pattern_type == pattern_type)

        return query.order_by(desc(CodePattern.confidence)).all()

    def clear_patterns(self, codebase_id: UUID) -> int:
        """
        Clear all patterns for a codebase index.

        Args:
            codebase_id: Codebase index ID

        Returns:
            Number of patterns deleted
        """
        result = (
            self.db.query(CodePattern)
            .filter(CodePattern.codebase_id == codebase_id)
            .delete()
        )
        self.db.commit()
        return result

    # =========================================================================
    # Context Building
    # =========================================================================

    def build_codebase_context(
        self,
        codebase_id: UUID,
        include_patterns: bool = True,
        max_symbols: int = 50,
    ) -> Dict[str, Any]:
        """
        Build codebase context for NAVI.

        Args:
            codebase_id: Codebase index ID
            include_patterns: Whether to include detected patterns
            max_symbols: Maximum symbols to include

        Returns:
            Dictionary with codebase context
        """
        index = self.get_index(codebase_id)
        if not index:
            return {}

        context = {
            "workspace_path": index.workspace_path,
            "workspace_name": index.workspace_name,
            "status": index.index_status,
            "stats": {
                "file_count": index.file_count,
                "symbol_count": index.symbol_count,
                "total_lines": index.total_lines,
            },
            "symbols": {},
            "patterns": [],
        }

        # Get symbol summary by type
        symbol_counts = (
            self.db.query(
                CodeSymbol.symbol_type,
                func.count(CodeSymbol.id).label("count"),
            )
            .filter(CodeSymbol.codebase_id == codebase_id)
            .group_by(CodeSymbol.symbol_type)
            .all()
        )
        context["symbols"]["by_type"] = {t: c for t, c in symbol_counts}

        # Get top symbols (by file path for organization)
        top_symbols = (
            self.db.query(CodeSymbol)
            .filter(CodeSymbol.codebase_id == codebase_id)
            .order_by(CodeSymbol.file_path)
            .limit(max_symbols)
            .all()
        )
        context["symbols"]["sample"] = [
            {
                "name": s.symbol_name,
                "type": s.symbol_type,
                "file": s.file_path,
                "line": s.line_start,
            }
            for s in top_symbols
        ]

        # Include patterns if requested
        if include_patterns:
            patterns = self.get_patterns(codebase_id, min_confidence=0.6)
            context["patterns"] = [
                {
                    "type": p.pattern_type,
                    "name": p.pattern_name,
                    "confidence": p.confidence,
                    "occurrences": p.occurrences,
                }
                for p in patterns
            ]

        return context


def get_codebase_memory_service(db: Session) -> CodebaseMemoryService:
    """Factory function to create CodebaseMemoryService."""
    return CodebaseMemoryService(db)
