"""
Workspace RAG - Full Codebase Understanding with Semantic Search

Provides:
1. Code indexing with embeddings
2. Semantic search across entire codebase
3. Dependency graph analysis
4. Context-aware code retrieval
5. Smart chunking for large files

This enables NAVI to understand the ENTIRE codebase, not just individual files.
"""

import os
import re
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
import fnmatch

logger = logging.getLogger(__name__)

# Track in-flight background indexing tasks to prevent duplicate indexers
_indexing_in_progress: set[str] = set()


# ============================================================
# CONFIGURATION
# ============================================================

# File extensions to index
INDEXABLE_EXTENSIONS = {
    # Languages
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".kt",
    ".scala",
    ".go",
    ".rs",
    ".rb",
    ".php",
    ".cs",
    ".cpp",
    ".c",
    ".h",
    ".hpp",
    ".swift",
    ".m",
    ".mm",
    ".lua",
    ".r",
    ".jl",
    ".ex",
    ".exs",
    ".clj",
    ".cljs",
    ".hs",
    ".ml",
    ".fs",
    ".erl",
    ".elm",
    # Web
    ".html",
    ".css",
    ".scss",
    ".sass",
    ".less",
    ".vue",
    ".svelte",
    # Config
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".xml",
    ".ini",
    ".env.example",
    # Data
    ".sql",
    ".graphql",
    ".prisma",
    # Docs
    ".md",
    ".mdx",
    ".rst",
    ".txt",
    # DevOps
    ".dockerfile",
    ".tf",
    ".hcl",
    # Shell
    ".sh",
    ".bash",
    ".zsh",
    ".ps1",
}

# Directories to skip
SKIP_DIRECTORIES = {
    "node_modules",
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "venv",
    ".venv",
    "env",
    ".env",
    "dist",
    "build",
    "target",
    "out",
    ".next",
    ".nuxt",
    ".cache",
    "coverage",
    ".coverage",
    ".tox",
    "vendor",
    "packages",
    ".idea",
    ".vscode",
    "*.egg-info",
}

# Max file size to index (1MB)
MAX_FILE_SIZE = 1024 * 1024

# Chunk size for large files
CHUNK_SIZE = 2000  # characters
CHUNK_OVERLAP = 200  # overlap between chunks


# ============================================================
# DATA CLASSES
# ============================================================


class CodeChunkType(Enum):
    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    MODULE = "module"
    IMPORT = "import"
    COMMENT = "comment"
    CONFIG = "config"
    TEST = "test"
    GENERIC = "generic"


@dataclass
class CodeChunk:
    """A chunk of code with metadata for RAG retrieval"""

    id: str
    file_path: str
    content: str
    chunk_type: CodeChunkType
    start_line: int
    end_line: int

    # Semantic info
    name: Optional[str] = None  # function/class name
    signature: Optional[str] = None  # function signature
    docstring: Optional[str] = None

    # Dependencies
    imports: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)  # Other symbols referenced

    # Embedding (populated after indexing)
    embedding: Optional[List[float]] = None

    # Metadata
    language: str = "unknown"
    last_modified: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "file_path": self.file_path,
            "content": (
                self.content[:500] + "..." if len(self.content) > 500 else self.content
            ),
            "chunk_type": self.chunk_type.value,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "name": self.name,
            "signature": self.signature,
            "language": self.language,
        }


@dataclass
class FileIndex:
    """Index entry for a single file"""

    path: str
    relative_path: str
    language: str
    size: int
    last_modified: str
    content_hash: str
    chunks: List[CodeChunk] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "relative_path": self.relative_path,
            "language": self.language,
            "size": self.size,
            "chunks_count": len(self.chunks),
            "imports": self.imports[:10],
            "exports": self.exports[:10],
        }


@dataclass
class DependencyEdge:
    """An edge in the dependency graph"""

    source: str  # file path
    target: str  # file path or module name
    edge_type: str  # "import", "extends", "implements", "uses"


@dataclass
class WorkspaceIndex:
    """Complete index of a workspace"""

    workspace_path: str
    files: Dict[str, FileIndex] = field(default_factory=dict)
    chunks: List[CodeChunk] = field(default_factory=list)
    dependencies: List[DependencyEdge] = field(default_factory=list)

    # Metadata
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    total_files: int = 0
    total_chunks: int = 0
    total_lines: int = 0

    # Symbol table for quick lookup
    symbols: Dict[str, List[str]] = field(default_factory=dict)  # name -> [file_paths]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workspace_path": self.workspace_path,
            "total_files": self.total_files,
            "total_chunks": self.total_chunks,
            "total_lines": self.total_lines,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "languages": list(set(f.language for f in self.files.values())),
        }


# ============================================================
# CODE PARSER - Extract semantic chunks from code
# ============================================================


class CodeParser:
    """Parse code files into semantic chunks"""

    # Language detection by extension
    LANGUAGE_MAP = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".java": "java",
        ".kt": "kotlin",
        ".scala": "scala",
        ".go": "go",
        ".rs": "rust",
        ".rb": "ruby",
        ".php": "php",
        ".cs": "csharp",
        ".cpp": "cpp",
        ".c": "c",
        ".h": "c",
        ".hpp": "cpp",
        ".swift": "swift",
        ".sql": "sql",
        ".md": "markdown",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".html": "html",
        ".css": "css",
        ".scss": "scss",
        ".vue": "vue",
        ".svelte": "svelte",
        ".tf": "terraform",
        ".sh": "bash",
        ".bash": "bash",
    }

    # Regex patterns for extracting code structures
    PATTERNS = {
        "python": {
            "function": r"^(?:async\s+)?def\s+(\w+)\s*\([^)]*\)(?:\s*->.*?)?:",
            "class": r"^class\s+(\w+)(?:\([^)]*\))?:",
            "import": r"^(?:from\s+[\w.]+\s+)?import\s+.+",
            "docstring": r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'',
        },
        "javascript": {
            "function": r"(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\([^)]*\)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>",
            "class": r"(?:export\s+)?class\s+(\w+)(?:\s+extends\s+\w+)?",
            "import": r"^import\s+.+from|^const\s+.+=\s*require\(",
        },
        "typescript": {
            "function": r"(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*[<(]|(?:const|let)\s+(\w+)\s*(?::\s*[\w<>[\],\s]+)?\s*=\s*(?:async\s+)?\([^)]*\)\s*(?::\s*[\w<>[\],\s]+)?\s*=>",
            "class": r"(?:export\s+)?(?:abstract\s+)?class\s+(\w+)",
            "interface": r"(?:export\s+)?interface\s+(\w+)",
            "type": r"(?:export\s+)?type\s+(\w+)",
            "import": r"^import\s+.+from",
        },
        "java": {
            "function": r"(?:public|private|protected)?\s*(?:static)?\s*(?:\w+(?:<[\w<>,\s]+>)?)\s+(\w+)\s*\([^)]*\)",
            "class": r"(?:public|private)?\s*(?:abstract|final)?\s*class\s+(\w+)",
            "interface": r"(?:public)?\s*interface\s+(\w+)",
            "import": r"^import\s+[\w.]+;",
        },
        "go": {
            "function": r"^func\s+(?:\([^)]+\)\s+)?(\w+)\s*\([^)]*\)",
            "struct": r"^type\s+(\w+)\s+struct",
            "interface": r"^type\s+(\w+)\s+interface",
            "import": r'^import\s+(?:\([\s\S]*?\)|"[\w/.-]+")',
        },
        "rust": {
            "function": r"(?:pub\s+)?(?:async\s+)?fn\s+(\w+)",
            "struct": r"(?:pub\s+)?struct\s+(\w+)",
            "enum": r"(?:pub\s+)?enum\s+(\w+)",
            "trait": r"(?:pub\s+)?trait\s+(\w+)",
            "impl": r"impl(?:<[^>]+>)?\s+(?:(\w+)\s+for\s+)?(\w+)",
            "import": r"^use\s+[\w:]+",
        },
    }

    @classmethod
    def detect_language(cls, file_path: str) -> str:
        """Detect language from file extension"""
        ext = Path(file_path).suffix.lower()
        return cls.LANGUAGE_MAP.get(ext, "unknown")

    @classmethod
    def parse_file(cls, file_path: str, content: str) -> List[CodeChunk]:
        """Parse a file into semantic chunks"""
        language = cls.detect_language(file_path)
        chunks = []

        # Get patterns for this language
        patterns = cls.PATTERNS.get(language, {})

        if not patterns:
            # Fall back to generic chunking
            return cls._generic_chunk(file_path, content, language)

        lines = content.split("\n")

        # Extract imports first
        imports = cls._extract_imports(content, patterns.get("import"))

        # Find all functions/classes
        if "function" in patterns:
            chunks.extend(
                cls._extract_functions(
                    file_path, content, lines, patterns["function"], language
                )
            )

        if "class" in patterns:
            chunks.extend(
                cls._extract_classes(
                    file_path, content, lines, patterns["class"], language
                )
            )

        # If no structured chunks found, use generic chunking
        if not chunks:
            chunks = cls._generic_chunk(file_path, content, language)

        # Add imports to each chunk
        for chunk in chunks:
            chunk.imports = imports

        return chunks

    @classmethod
    def _extract_imports(cls, content: str, pattern: Optional[str]) -> List[str]:
        """Extract import statements"""
        if not pattern:
            return []

        imports = []
        for match in re.finditer(pattern, content, re.MULTILINE):
            imports.append(match.group(0).strip())
        return imports

    @classmethod
    def _extract_functions(
        cls,
        file_path: str,
        content: str,
        lines: List[str],
        pattern: str,
        language: str,
    ) -> List[CodeChunk]:
        """Extract function definitions"""
        chunks = []

        for match in re.finditer(pattern, content, re.MULTILINE):
            # Get function name
            name = None
            for group in match.groups():
                if group:
                    name = group
                    break

            if not name:
                continue

            # Find line number
            start_pos = match.start()
            start_line = content[:start_pos].count("\n") + 1

            # Find function end (simplified - look for next function or class)
            end_line = cls._find_block_end(lines, start_line - 1, language)

            # Extract content
            func_content = "\n".join(lines[start_line - 1 : end_line])

            # Extract docstring if present
            docstring = cls._extract_docstring(func_content, language)

            chunk_id = hashlib.md5(
                f"{file_path}:{name}:{start_line}".encode()
            ).hexdigest()[:12]

            chunks.append(
                CodeChunk(
                    id=chunk_id,
                    file_path=file_path,
                    content=func_content,
                    chunk_type=CodeChunkType.FUNCTION,
                    start_line=start_line,
                    end_line=end_line,
                    name=name,
                    signature=match.group(0).strip(),
                    docstring=docstring,
                    language=language,
                )
            )

        return chunks

    @classmethod
    def _extract_classes(
        cls,
        file_path: str,
        content: str,
        lines: List[str],
        pattern: str,
        language: str,
    ) -> List[CodeChunk]:
        """Extract class definitions"""
        chunks = []

        for match in re.finditer(pattern, content, re.MULTILINE):
            name = match.group(1) if match.groups() else None
            if not name:
                continue

            start_pos = match.start()
            start_line = content[:start_pos].count("\n") + 1
            end_line = cls._find_block_end(lines, start_line - 1, language)

            class_content = "\n".join(lines[start_line - 1 : end_line])
            docstring = cls._extract_docstring(class_content, language)

            chunk_id = hashlib.md5(
                f"{file_path}:{name}:{start_line}".encode()
            ).hexdigest()[:12]

            chunks.append(
                CodeChunk(
                    id=chunk_id,
                    file_path=file_path,
                    content=class_content,
                    chunk_type=CodeChunkType.CLASS,
                    start_line=start_line,
                    end_line=end_line,
                    name=name,
                    signature=match.group(0).strip(),
                    docstring=docstring,
                    language=language,
                )
            )

        return chunks

    @classmethod
    def _find_block_end(cls, lines: List[str], start_idx: int, language: str) -> int:
        """Find the end of a code block (function/class)"""
        if language == "python":
            # Python uses indentation
            if start_idx >= len(lines):
                return len(lines)

            start_indent = len(lines[start_idx]) - len(lines[start_idx].lstrip())

            for i in range(start_idx + 1, len(lines)):
                line = lines[i]
                if not line.strip():  # Skip empty lines
                    continue

                current_indent = len(line) - len(line.lstrip())
                if current_indent <= start_indent and line.strip():
                    return i

            return len(lines)

        else:
            # Brace-based languages - count braces
            brace_count = 0
            started = False

            for i in range(start_idx, len(lines)):
                line = lines[i]
                brace_count += line.count("{") - line.count("}")

                if "{" in line:
                    started = True

                if started and brace_count <= 0:
                    return i + 1

            return len(lines)

    @classmethod
    def _extract_docstring(cls, content: str, language: str) -> Optional[str]:
        """Extract docstring from code"""
        if language == "python":
            match = re.search(r'"""([\s\S]*?)"""|\'\'\'([\s\S]*?)\'\'\'', content)
            if match:
                return (match.group(1) or match.group(2)).strip()

        elif language in ["javascript", "typescript", "java", "go", "rust"]:
            # JSDoc / JavaDoc style
            match = re.search(r"/\*\*([\s\S]*?)\*/", content)
            if match:
                return match.group(1).strip()

        return None

    @classmethod
    def _generic_chunk(
        cls, file_path: str, content: str, language: str
    ) -> List[CodeChunk]:
        """Fall back to generic chunking for unsupported languages"""
        chunks = []
        content.split("\n")

        # Split into chunks of CHUNK_SIZE characters with overlap
        for i in range(0, len(content), CHUNK_SIZE - CHUNK_OVERLAP):
            chunk_content = content[i : i + CHUNK_SIZE]

            # Find line numbers
            start_line = content[:i].count("\n") + 1
            end_line = start_line + chunk_content.count("\n")

            chunk_id = hashlib.md5(f"{file_path}:{i}".encode()).hexdigest()[:12]

            chunks.append(
                CodeChunk(
                    id=chunk_id,
                    file_path=file_path,
                    content=chunk_content,
                    chunk_type=CodeChunkType.GENERIC,
                    start_line=start_line,
                    end_line=end_line,
                    language=language,
                )
            )

        return chunks


# ============================================================
# EMBEDDINGS - Generate embeddings for semantic search
# ============================================================


class EmbeddingProvider:
    """Generate embeddings for code chunks"""

    # Simple TF-IDF-like scoring for local search (no API needed)
    # For production, use OpenAI embeddings or local model

    @classmethod
    def generate_embedding(cls, text: str) -> List[float]:
        """Generate a simple embedding (local, no API)"""
        # This is a simplified embedding for demonstration
        # In production, use OpenAI text-embedding-ada-002 or similar

        # Tokenize and create term frequencies
        tokens = re.findall(r"\b\w+\b", text.lower())
        vocab = list(set(tokens))[:100]  # Limit vocab size

        # Create simple frequency-based embedding
        embedding = []
        for word in vocab:
            freq = tokens.count(word) / len(tokens) if tokens else 0
            embedding.append(freq)

        # Pad to fixed size
        while len(embedding) < 100:
            embedding.append(0.0)

        return embedding[:100]

    @classmethod
    async def generate_embedding_async(
        cls, text: str, provider: str = "local"
    ) -> List[float]:
        """Generate embedding asynchronously"""
        if provider == "local":
            return cls.generate_embedding(text)

        elif provider == "openai":
            # Use OpenAI embeddings API
            try:
                import httpx

                api_key = os.environ.get("OPENAI_API_KEY")
                if not api_key:
                    return cls.generate_embedding(text)

                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "https://api.openai.com/v1/embeddings",
                        headers={"Authorization": f"Bearer {api_key}"},
                        json={
                            "model": "text-embedding-ada-002",
                            "input": text[:8000],  # Truncate to token limit
                        },
                        timeout=30.0,
                    )

                    if response.status_code == 200:
                        return response.json()["data"][0]["embedding"]
            except Exception as e:
                logger.warning(f"OpenAI embedding failed: {e}, falling back to local")

        return cls.generate_embedding(text)

    @classmethod
    def cosine_similarity(cls, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two embeddings"""
        if not a or not b or len(a) != len(b):
            return 0.0

        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)


# ============================================================
# WORKSPACE INDEXER - Index entire codebase
# ============================================================


class WorkspaceIndexer:
    """Index an entire workspace for RAG"""

    @classmethod
    async def index_workspace(
        cls,
        workspace_path: str,
        generate_embeddings: bool = True,
        embedding_provider: str = "local",
        on_progress: Optional[callable] = None,
    ) -> WorkspaceIndex:
        """
        Index all code files in a workspace.

        Args:
            workspace_path: Path to the workspace root
            generate_embeddings: Whether to generate embeddings for semantic search
            embedding_provider: "local" or "openai"
            on_progress: Callback for progress updates
        """
        index = WorkspaceIndex(workspace_path=workspace_path)

        # Find all indexable files
        files_to_index = cls._find_indexable_files(workspace_path)
        total_files = len(files_to_index)

        if on_progress:
            await on_progress({"type": "start", "total_files": total_files})

        # Index each file
        for i, file_path in enumerate(files_to_index):
            try:
                file_index = await cls._index_file(
                    file_path, workspace_path, generate_embeddings, embedding_provider
                )
                if file_index:
                    index.files[file_path] = file_index
                    index.chunks.extend(file_index.chunks)
                    index.total_lines += len(open(file_path).readlines())

                    # Update symbol table
                    for chunk in file_index.chunks:
                        if chunk.name:
                            if chunk.name not in index.symbols:
                                index.symbols[chunk.name] = []
                            index.symbols[chunk.name].append(file_path)

                    # Track dependencies
                    for imp in file_index.imports:
                        index.dependencies.append(
                            DependencyEdge(
                                source=file_path,
                                target=imp,
                                edge_type="import",
                            )
                        )

            except Exception as e:
                logger.warning(f"Failed to index {file_path}: {e}")

            if on_progress and i % 10 == 0:
                await on_progress(
                    {
                        "type": "progress",
                        "current": i + 1,
                        "total": total_files,
                        "file": file_path,
                    }
                )

        index.total_files = len(index.files)
        index.total_chunks = len(index.chunks)
        index.updated_at = datetime.utcnow().isoformat()

        if on_progress:
            await on_progress(
                {
                    "type": "complete",
                    "total_files": index.total_files,
                    "total_chunks": index.total_chunks,
                }
            )

        return index

    @classmethod
    def _find_indexable_files(cls, workspace_path: str) -> List[str]:
        """Find all files that should be indexed"""
        files = []

        for root, dirs, filenames in os.walk(workspace_path):
            # Skip excluded directories
            dirs[:] = [
                d for d in dirs if d not in SKIP_DIRECTORIES and not d.startswith(".")
            ]

            for filename in filenames:
                file_path = os.path.join(root, filename)

                # Check extension
                ext = Path(filename).suffix.lower()
                if ext not in INDEXABLE_EXTENSIONS:
                    continue

                # Check file size
                try:
                    if os.path.getsize(file_path) > MAX_FILE_SIZE:
                        continue
                except OSError:
                    continue

                files.append(file_path)

        return files

    @classmethod
    async def _index_file(
        cls,
        file_path: str,
        workspace_path: str,
        generate_embeddings: bool,
        embedding_provider: str,
    ) -> Optional[FileIndex]:
        """Index a single file"""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            # Parse into chunks
            chunks = CodeParser.parse_file(file_path, content)

            # Generate embeddings if requested
            if generate_embeddings:
                for chunk in chunks:
                    # Create searchable text
                    search_text = f"{chunk.name or ''} {chunk.signature or ''} {chunk.docstring or ''} {chunk.content[:500]}"
                    chunk.embedding = await EmbeddingProvider.generate_embedding_async(
                        search_text,
                        embedding_provider,
                    )

            # Get file metadata
            stat = os.stat(file_path)
            content_hash = hashlib.md5(content.encode()).hexdigest()

            # Extract imports/exports
            language = CodeParser.detect_language(file_path)
            imports = []
            exports = []

            for chunk in chunks:
                imports.extend(chunk.imports)
                if chunk.name:
                    exports.append(chunk.name)

            return FileIndex(
                path=file_path,
                relative_path=os.path.relpath(file_path, workspace_path),
                language=language,
                size=stat.st_size,
                last_modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                content_hash=content_hash,
                chunks=chunks,
                imports=list(set(imports)),
                exports=list(set(exports)),
            )

        except Exception as e:
            logger.warning(f"Failed to index file {file_path}: {e}")
            return None


# ============================================================
# SEMANTIC SEARCH - Find relevant code
# ============================================================


class SemanticSearch:
    """Search the workspace index semantically"""

    @classmethod
    async def search(
        cls,
        query: str,
        index: WorkspaceIndex,
        top_k: int = 10,
        min_score: float = 0.1,
        file_filter: Optional[List[str]] = None,
        language_filter: Optional[List[str]] = None,
    ) -> List[Tuple[CodeChunk, float]]:
        """
        Search for relevant code chunks.

        Args:
            query: Natural language query or code snippet
            index: The workspace index to search
            top_k: Number of results to return
            min_score: Minimum similarity score
            file_filter: Only search in these files (glob patterns)
            language_filter: Only search in these languages

        Returns:
            List of (chunk, score) tuples sorted by relevance
        """
        # Generate query embedding
        query_embedding = await EmbeddingProvider.generate_embedding_async(query)

        results = []

        for chunk in index.chunks:
            # Apply filters
            if file_filter:
                if not any(
                    fnmatch.fnmatch(chunk.file_path, pattern) for pattern in file_filter
                ):
                    continue

            if language_filter:
                if chunk.language not in language_filter:
                    continue

            # Calculate similarity
            if chunk.embedding:
                score = EmbeddingProvider.cosine_similarity(
                    query_embedding, chunk.embedding
                )
            else:
                # Fall back to keyword matching
                score = cls._keyword_score(query, chunk)

            if score >= min_score:
                results.append((chunk, score))

        # Sort by score
        results.sort(key=lambda x: x[1], reverse=True)

        return results[:top_k]

    @classmethod
    def _keyword_score(cls, query: str, chunk: CodeChunk) -> float:
        """Simple keyword matching score"""
        query_tokens = set(re.findall(r"\b\w+\b", query.lower()))
        chunk_tokens = set(re.findall(r"\b\w+\b", chunk.content.lower()))

        if not query_tokens or not chunk_tokens:
            return 0.0

        intersection = query_tokens & chunk_tokens
        return len(intersection) / len(query_tokens)

    @classmethod
    def find_symbol(cls, symbol_name: str, index: WorkspaceIndex) -> List[CodeChunk]:
        """Find all definitions of a symbol"""
        chunks = []

        for chunk in index.chunks:
            if chunk.name == symbol_name:
                chunks.append(chunk)

        return chunks

    @classmethod
    def find_references(
        cls, symbol_name: str, index: WorkspaceIndex
    ) -> List[CodeChunk]:
        """Find all references to a symbol"""
        chunks = []

        for chunk in index.chunks:
            if symbol_name in chunk.content and chunk.name != symbol_name:
                chunks.append(chunk)

        return chunks

    @classmethod
    def get_file_context(cls, file_path: str, index: WorkspaceIndex) -> Dict[str, Any]:
        """Get full context for a file including dependencies"""
        file_index = index.files.get(file_path)
        if not file_index:
            return {}

        # Find files that import this file
        imported_by = []
        for dep in index.dependencies:
            if file_path in dep.target or file_index.relative_path in dep.target:
                imported_by.append(dep.source)

        # Find files this file imports
        imports = []
        for dep in index.dependencies:
            if dep.source == file_path:
                imports.append(dep.target)

        return {
            "file": file_index.to_dict(),
            "chunks": [c.to_dict() for c in file_index.chunks],
            "imports": imports,
            "imported_by": imported_by,
        }


# ============================================================
# STORAGE - Persist index
# ============================================================

_workspace_indexes: Dict[str, WorkspaceIndex] = {}


def store_index(index: WorkspaceIndex) -> None:
    """Store a workspace index"""
    _workspace_indexes[index.workspace_path] = index


def get_index(workspace_path: str) -> Optional[WorkspaceIndex]:
    """Get a workspace index"""
    return _workspace_indexes.get(workspace_path)


def list_indexes() -> List[str]:
    """List all indexed workspaces"""
    return list(_workspace_indexes.keys())


# ============================================================
# PUBLIC API
# ============================================================


async def index_workspace(
    workspace_path: str,
    force_reindex: bool = False,
    on_progress: Optional[callable] = None,
) -> Dict[str, Any]:
    """
    Index a workspace for RAG search.

    Returns index statistics.
    """
    # Check if already indexed
    existing = get_index(workspace_path)
    if existing and not force_reindex:
        return existing.to_dict()

    # Index the workspace
    index = await WorkspaceIndexer.index_workspace(
        workspace_path,
        generate_embeddings=True,
        on_progress=on_progress,
    )

    # Store it
    store_index(index)

    return index.to_dict()


async def search_codebase(
    workspace_path: str,
    query: str,
    top_k: int = 10,
    allow_background_indexing: bool = True,
) -> List[Dict[str, Any]]:
    """
    Search the codebase for relevant code.

    Returns list of relevant code chunks with scores.

    Args:
        workspace_path: Path to workspace
        query: Search query
        top_k: Number of results to return
        allow_background_indexing: If True, trigger background indexing for next time
    """
    index = get_index(workspace_path)
    if not index:
        # OPTIMIZATION: Don't block the request to index
        # Instead, trigger background indexing for next time
        if allow_background_indexing:
            import asyncio

            # Only start background indexing if not already in progress
            if workspace_path not in _indexing_in_progress:
                logger.info(
                    f"[RAG] No index found for {workspace_path} - scheduling background indexing"
                )
                # Mark as in progress BEFORE creating task to prevent race condition
                _indexing_in_progress.add(workspace_path)

                async def _run_background_indexer() -> None:
                    try:
                        await _background_index_workspace(workspace_path)
                    finally:
                        _indexing_in_progress.discard(workspace_path)

                # Fire and forget - don't await
                asyncio.create_task(_run_background_indexer())
            else:
                logger.debug(
                    f"[RAG] Background indexing already in progress for {workspace_path}"
                )

        # Return empty for now - next request will have index ready
        return []

    results = await SemanticSearch.search(query, index, top_k=top_k)

    return [
        {
            "chunk": chunk.to_dict(),
            "score": score,
            "file_path": chunk.file_path,
            "content_preview": (
                chunk.content[:300] + "..."
                if len(chunk.content) > 300
                else chunk.content
            ),
        }
        for chunk, score in results
    ]


async def _background_index_workspace(workspace_path: str) -> None:
    """
    Index workspace in background without blocking the request.

    This allows the FIRST request to return quickly (without RAG),
    while subsequent requests will have the index ready.

    Note: Caller is responsible for managing _indexing_in_progress set.
    """
    try:
        logger.info(f"[RAG] Starting background indexing for {workspace_path}")
        start_time = __import__("time").time()

        await index_workspace(workspace_path, force_reindex=False)

        elapsed = __import__("time").time() - start_time
        logger.info(
            f"[RAG] Background indexing completed for {workspace_path} "
            f"in {elapsed:.2f}s - future requests will use this index"
        )
    except Exception as e:
        logger.error(f"[RAG] Background indexing failed for {workspace_path}: {e}")
        raise  # Re-raise to trigger finally cleanup in wrapper


async def get_context_for_task(
    workspace_path: str,
    task_description: str,
    max_context_tokens: int = 8000,
) -> str:
    """
    Get relevant codebase context for a task.

    This is the main function NAVI uses to understand the codebase.
    Returns a formatted string with relevant code context.
    """
    results = await search_codebase(workspace_path, task_description, top_k=20)

    context_parts = ["=== RELEVANT CODEBASE CONTEXT ===\n"]
    total_chars = 0
    max_chars = max_context_tokens * 4  # Rough estimate

    for result in results:
        chunk = result["chunk"]
        content = result["content_preview"]

        section = f"""
--- {chunk['file_path']}:{chunk['start_line']} ({chunk['chunk_type']}) ---
{chunk.get('signature', '')}
{content}
"""

        if total_chars + len(section) > max_chars:
            break

        context_parts.append(section)
        total_chars += len(section)

    return "\n".join(context_parts)


# ============================================================
# DATABASE PERSISTENCE - Save and load indexes to/from database
# ============================================================


async def persist_workspace_index(
    workspace_path: str,
    user_id: int,
    org_id: Optional[int] = None,
    db: Optional[Any] = None,
) -> bool:
    """
    Persist workspace index to database for cross-session memory.

    Args:
        workspace_path: Path to the workspace
        user_id: User ID for the index
        org_id: Optional organization ID
        db: SQLAlchemy database session

    Returns:
        True if successful, False otherwise
    """
    global _workspace_indexes

    if workspace_path not in _workspace_indexes:
        logger.warning(f"No index found for {workspace_path}")
        return False

    if not db:
        logger.warning("No database session provided for persistence")
        return False

    try:
        from backend.services.memory.codebase_memory import CodebaseMemoryService

        memory_service = CodebaseMemoryService(db)
        index = _workspace_indexes[workspace_path]

        # Create or get existing codebase index
        workspace_name = Path(workspace_path).name
        codebase_index = memory_service.create_index(
            workspace_path=workspace_path,
            user_id=user_id,
            org_id=org_id,
            workspace_name=workspace_name,
            index_config={
                "total_files": index.total_files,
                "total_chunks": index.total_chunks,
                "total_lines": index.total_lines,
            },
        )

        # Store symbols/chunks with embeddings
        symbols_stored = 0
        for chunk in index.chunks[:500]:  # Limit to 500 most important chunks
            try:
                await memory_service.add_symbol(
                    codebase_id=codebase_index.id,
                    symbol_type=chunk.chunk_type.value,
                    symbol_name=chunk.name or f"chunk_{chunk.id}",
                    file_path=chunk.file_path,
                    line_start=chunk.start_line,
                    line_end=chunk.end_line,
                    language=chunk.language,
                    code_snippet=chunk.content[:2000] if chunk.content else None,
                    signature=chunk.signature,
                    documentation=chunk.docstring,
                    generate_embedding=False,  # Use pre-computed embeddings if available
                )
                symbols_stored += 1
            except Exception as e:
                logger.warning(f"Failed to store symbol {chunk.name}: {e}")
                continue

        # Update index status
        memory_service.update_index_status(
            index_id=codebase_index.id,
            status="ready",
            file_count=index.total_files,
            symbol_count=symbols_stored,
            total_lines=index.total_lines,
        )

        logger.info(f"Persisted {symbols_stored} symbols for {workspace_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to persist workspace index: {e}")
        return False


async def load_workspace_index(
    workspace_path: str,
    user_id: Optional[int] = None,
    db: Optional[Any] = None,
) -> Optional[WorkspaceIndex]:
    """
    Load workspace index from database.

    Args:
        workspace_path: Path to the workspace
        user_id: Optional user ID filter
        db: SQLAlchemy database session

    Returns:
        WorkspaceIndex if found, None otherwise
    """
    global _workspace_indexes

    # Check if already loaded in memory
    if workspace_path in _workspace_indexes:
        logger.info(f"Using in-memory index for {workspace_path}")
        return _workspace_indexes[workspace_path]

    if not db:
        logger.warning("No database session provided for loading")
        return None

    try:
        from backend.services.memory.codebase_memory import CodebaseMemoryService

        memory_service = CodebaseMemoryService(db)

        # Get existing codebase index
        codebase_index = memory_service.get_index_by_path(workspace_path, user_id)
        if not codebase_index:
            logger.info(f"No persisted index found for {workspace_path}")
            return None

        if codebase_index.index_status != "ready":
            logger.info(
                f"Index for {workspace_path} is not ready (status: {codebase_index.index_status})"
            )
            return None

        # Load symbols from database
        from backend.database.models.memory import CodeSymbol

        symbols = (
            db.query(CodeSymbol)
            .filter(CodeSymbol.codebase_id == codebase_index.id)
            .limit(500)
            .all()
        )

        if not symbols:
            logger.info(f"No symbols found for {workspace_path}")
            return None

        # Reconstruct WorkspaceIndex from database
        index = WorkspaceIndex(workspace_path=workspace_path)
        index.total_files = codebase_index.file_count or 0
        index.total_lines = codebase_index.total_lines or 0
        index.created_at = (
            codebase_index.created_at.isoformat() if codebase_index.created_at else ""
        )
        index.updated_at = (
            codebase_index.updated_at.isoformat() if codebase_index.updated_at else ""
        )

        # Convert symbols to chunks
        for symbol in symbols:
            chunk = CodeChunk(
                id=str(symbol.id),
                file_path=symbol.file_path,
                content=symbol.code_snippet or "",
                chunk_type=(
                    CodeChunkType(symbol.symbol_type)
                    if symbol.symbol_type in [t.value for t in CodeChunkType]
                    else CodeChunkType.GENERIC
                ),
                start_line=symbol.line_start,
                end_line=symbol.line_end,
                name=symbol.symbol_name,
                signature=symbol.signature,
                docstring=symbol.documentation,
                language=symbol.language or "unknown",
            )
            index.chunks.append(chunk)

            # Update symbol table
            if symbol.symbol_name:
                if symbol.symbol_name not in index.symbols:
                    index.symbols[symbol.symbol_name] = []
                index.symbols[symbol.symbol_name].append(symbol.file_path)

        index.total_chunks = len(index.chunks)

        # Cache in memory
        _workspace_indexes[workspace_path] = index

        logger.info(
            f"Loaded {len(index.chunks)} symbols from database for {workspace_path}"
        )
        return index

    except Exception as e:
        logger.error(f"Failed to load workspace index: {e}")
        return None


async def has_persisted_index(
    workspace_path: str,
    user_id: Optional[int] = None,
    db: Optional[Any] = None,
) -> bool:
    """
    Check if a workspace has a persisted index in the database.

    Args:
        workspace_path: Path to the workspace
        user_id: Optional user ID filter
        db: SQLAlchemy database session

    Returns:
        True if a ready index exists, False otherwise
    """
    if not db:
        return False

    try:
        from backend.services.memory.codebase_memory import CodebaseMemoryService

        memory_service = CodebaseMemoryService(db)
        codebase_index = memory_service.get_index_by_path(workspace_path, user_id)

        return codebase_index is not None and codebase_index.index_status == "ready"

    except Exception as e:
        logger.error(f"Failed to check persisted index: {e}")
        return False
