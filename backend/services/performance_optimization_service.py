"""
Performance Optimization Service - Enterprise-grade scalability for large codebases
Provides streaming analysis, prioritized scanning, and intelligent context window management
"""

import asyncio
import time
import logging
from typing import Dict, List, Any, Optional, AsyncGenerator, Tuple
from dataclasses import dataclass
from pathlib import Path
import os
import fnmatch
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

@dataclass
class FileMetrics:
    """Performance metrics for a file"""
    path: str
    size_bytes: int
    line_count: int
    complexity_score: float  # 0.0 to 1.0
    last_modified: float
    priority_score: float    # Higher = more important
    analysis_time_ms: float

@dataclass
class ScanProgress:
    """Progress tracking for large codebase scans"""
    total_files: int
    processed_files: int
    skipped_files: int
    current_file: str
    elapsed_time_ms: float
    estimated_remaining_ms: float
    throughput_files_per_second: float

class PerformanceOptimizationService:
    """
    Enterprise performance optimization for large-scale code analysis
    
    Features:
    - Streaming file analysis with backpressure handling
    - Intelligent file prioritization based on importance
    - Context window management for LLM efficiency
    - Parallel processing with resource limiting
    - Progress tracking and estimation
    """
    
    def __init__(self, max_workers: int = 4, max_memory_mb: int = 512):
        self.max_workers = max_workers
        self.max_memory_mb = max_memory_mb
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        
        # Performance caching
        self.file_cache: Dict[str, FileMetrics] = {}
        self.analysis_cache: Dict[str, Any] = {}
        
        # Priority patterns for different file types
        self.priority_patterns = {
            'critical': [
                '**/config/**', '**/settings/**', '**/.env*', '**/security/**',
                '**/auth/**', '**/main.*', '**/app.*', '**/server.*'
            ],
            'high': [
                '**/api/**', '**/models/**', '**/services/**', '**/controllers/**',
                '**/core/**', '**/lib/**', '**/utils/**'
            ],
            'medium': [
                '**/components/**', '**/views/**', '**/handlers/**', '**/middleware/**',
                '**/routes/**', '**/*.py', '**/*.js', '**/*.ts', '**/*.java'
            ],
            'low': [
                '**/tests/**', '**/test/**', '**/*test*', '**/*spec*',
                '**/docs/**', '**/documentation/**', '**/*.md', '**/*.txt'
            ],
            'minimal': [
                '**/node_modules/**', '**/venv/**', '**/env/**', '**/.git/**',
                '**/__pycache__/**', '**/dist/**', '**/build/**'
            ]
        }
        
        # File exclusion patterns for performance
        self.exclusion_patterns = [
            '**/.git/**', '**/node_modules/**', '**/venv/**', '**/.venv/**',
            '**/__pycache__/**', '**/dist/**', '**/build/**', '**/*.pyc',
            '**/*.log', '**/*.tmp', '**/.DS_Store', '**/Thumbs.db'
        ]

    async def scan_codebase_streaming(
        self, 
        workspace_path: str,
        max_files: Optional[int] = None,
        file_extensions: Optional[List[str]] = None
    ) -> AsyncGenerator[Tuple[FileMetrics, ScanProgress], None]:
        """
        Stream file analysis results for large codebases with progress tracking
        
        Args:
            workspace_path: Root directory to scan
            max_files: Optional limit on number of files to process
            file_extensions: Optional filter for specific file types
            
        Yields:
            Tuple of (FileMetrics, ScanProgress) for each processed file
        """
        start_time = time.time()
        
        # Discover all files first for progress calculation
        all_files = list(self._discover_files(workspace_path, file_extensions))
        
        if max_files:
            all_files = all_files[:max_files]
        
        total_files = len(all_files)
        processed = 0
        skipped = 0
        
        logger.info(f"Starting streaming scan of {total_files} files in {workspace_path}")
        
        # Process files in priority order
        prioritized_files = self._prioritize_files(all_files)
        
        # Use semaphore to limit concurrent processing
        semaphore = asyncio.Semaphore(self.max_workers)
        
        async def process_file_batch(file_batch: List[str]) -> List[Optional[FileMetrics]]:
            """Process a batch of files concurrently"""
            async def process_single_file(file_path: str) -> Optional[FileMetrics]:
                async with semaphore:
                    return await self._analyze_file_performance(file_path)
            
            results = await asyncio.gather(
                *[process_single_file(f) for f in file_batch],
                return_exceptions=True
            )
            # Filter out exceptions and return only successful results
            return [result for result in results if isinstance(result, FileMetrics) or result is None]
        
        # Process in batches for memory efficiency
        batch_size = min(10, self.max_workers * 2)
        
        for i in range(0, len(prioritized_files), batch_size):
            batch = prioritized_files[i:i + batch_size]
            
            # Process batch
            results = await process_file_batch(batch)
            
            # Yield results
            for j, result in enumerate(results):
                current_file = batch[j]
                
                if isinstance(result, Exception):
                    logger.warning(f"Failed to analyze {current_file}: {result}")
                    skipped += 1
                    continue
                
                if result is None:
                    skipped += 1
                    continue
                
                processed += 1
                
                # Calculate progress
                elapsed_ms = (time.time() - start_time) * 1000
                throughput = processed / (elapsed_ms / 1000) if elapsed_ms > 0 else 0
                
                remaining_files = total_files - processed - skipped
                estimated_remaining_ms = (remaining_files / throughput * 1000) if throughput > 0 else 0
                
                progress = ScanProgress(
                    total_files=total_files,
                    processed_files=processed,
                    skipped_files=skipped,
                    current_file=current_file,
                    elapsed_time_ms=elapsed_ms,
                    estimated_remaining_ms=estimated_remaining_ms,
                    throughput_files_per_second=throughput
                )
                
                yield result, progress
        
        logger.info(f"Completed streaming scan: {processed} processed, {skipped} skipped in {elapsed_ms:.2f}ms")

    async def get_high_priority_files(
        self, 
        workspace_path: str, 
        limit: int = 20
    ) -> List[FileMetrics]:
        """
        Get highest priority files for immediate analysis
        
        Args:
            workspace_path: Root directory to scan
            limit: Maximum number of files to return
            
        Returns:
            List of FileMetrics sorted by priority (highest first)
        """
        high_priority_files = []
        
        async for file_metrics, _ in self.scan_codebase_streaming(workspace_path, max_files=limit * 3):
            high_priority_files.append(file_metrics)
            
            # Sort and maintain top N
            high_priority_files.sort(key=lambda f: f.priority_score, reverse=True)
            if len(high_priority_files) > limit:
                high_priority_files = high_priority_files[:limit]
        
        return high_priority_files

    def optimize_context_window(
        self, 
        files: List[FileMetrics], 
        max_tokens: int = 8000,
        tokens_per_line: float = 4.0
    ) -> List[FileMetrics]:
        """
        Optimize file selection to fit within LLM context window
        
        Args:
            files: List of candidate files
            max_tokens: Maximum token budget
            tokens_per_line: Estimated tokens per line of code
            
        Returns:
            Optimized list of files that fit within context window
        """
        # Sort by priority score descending
        sorted_files = sorted(files, key=lambda f: f.priority_score, reverse=True)
        
        selected_files = []
        total_tokens = 0
        
        for file_metrics in sorted_files:
            estimated_tokens = file_metrics.line_count * tokens_per_line
            
            if total_tokens + estimated_tokens <= max_tokens:
                selected_files.append(file_metrics)
                total_tokens += estimated_tokens
            else:
                # Try to include partial file content for very high priority files
                if file_metrics.priority_score > 0.8 and len(selected_files) < 3:
                    # Calculate how many lines we can include
                    remaining_tokens = max_tokens - total_tokens
                    max_lines = int(remaining_tokens / tokens_per_line)
                    
                    if max_lines > 10:  # Minimum useful content
                        # Create partial file metrics
                        partial_metrics = FileMetrics(
                            path=file_metrics.path,
                            size_bytes=file_metrics.size_bytes,
                            line_count=max_lines,  # Truncated
                            complexity_score=file_metrics.complexity_score,
                            last_modified=file_metrics.last_modified,
                            priority_score=file_metrics.priority_score * 0.7,  # Reduced for partial
                            analysis_time_ms=file_metrics.analysis_time_ms
                        )
                        selected_files.append(partial_metrics)
                        break
        
        logger.info(f"Context optimization: selected {len(selected_files)} files using ~{total_tokens} tokens")
        return selected_files

    async def _analyze_file_performance(self, file_path: str) -> Optional[FileMetrics]:
        """Analyze a single file for performance metrics"""
        try:
            # Check cache first
            cache_key = f"{file_path}:{os.path.getmtime(file_path)}"
            if cache_key in self.file_cache:
                return self.file_cache[cache_key]
            
            start_time = time.time()
            
            # Get file stats
            stat = os.stat(file_path)
            
            # Skip very large files that could cause memory issues
            if stat.st_size > self.max_memory_mb * 1024 * 1024:
                logger.warning(f"Skipping large file: {file_path} ({stat.st_size} bytes)")
                return None
            
            # Read file for analysis
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception as e:
                logger.warning(f"Could not read {file_path}: {e}")
                return None
            
            lines = content.split('\n')
            line_count = len(lines)
            
            # Calculate complexity score
            complexity = self._calculate_complexity(content, file_path)
            
            # Calculate priority score
            priority = self._calculate_priority_score(file_path, stat.st_size, complexity)
            
            analysis_time_ms = (time.time() - start_time) * 1000
            
            metrics = FileMetrics(
                path=file_path,
                size_bytes=stat.st_size,
                line_count=line_count,
                complexity_score=complexity,
                last_modified=stat.st_mtime,
                priority_score=priority,
                analysis_time_ms=analysis_time_ms
            )
            
            # Cache results
            self.file_cache[cache_key] = metrics
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error analyzing {file_path}: {e}")
            return None

    def _discover_files(
        self, 
        workspace_path: str, 
        file_extensions: Optional[List[str]] = None
    ) -> List[str]:
        """Discover all relevant files in workspace"""
        discovered_files = []
        workspace_path_obj = Path(workspace_path).resolve()
        
        # Default extensions if none specified
        if file_extensions is None:
            file_extensions = ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.go', '.rs', '.php', '.rb']
        
        for root, dirs, files in os.walk(workspace_path_obj):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if not any(
                fnmatch.fnmatch(os.path.join(root, d), pattern) 
                for pattern in self.exclusion_patterns
            )]
            
            for file in files:
                file_path = os.path.join(root, file)
                
                # Check file extension
                if file_extensions and not any(file.endswith(ext) for ext in file_extensions):
                    continue
                
                # Skip excluded files
                if any(fnmatch.fnmatch(file_path, pattern) for pattern in self.exclusion_patterns):
                    continue
                
                discovered_files.append(file_path)
        
        return discovered_files

    def _prioritize_files(self, files: List[str]) -> List[str]:
        """Sort files by priority for processing"""
        def get_priority_value(file_path: str) -> float:
            path_lower = file_path.lower()
            
            # Check priority patterns
            for priority_level, patterns in self.priority_patterns.items():
                for pattern in patterns:
                    if fnmatch.fnmatch(path_lower, pattern.lower()):
                        return {
                            'critical': 1.0,
                            'high': 0.8,
                            'medium': 0.6,
                            'low': 0.4,
                            'minimal': 0.2
                        }.get(priority_level, 0.6)
            
            return 0.6  # Default medium priority
        
        return sorted(files, key=get_priority_value, reverse=True)

    def _calculate_complexity(self, content: str, file_path: str) -> float:
        """Calculate code complexity score (0.0 to 1.0)"""
        try:
            # Basic complexity indicators
            lines = content.split('\n')
            non_empty_lines = [line for line in lines if line.strip()]
            
            # Count complexity indicators
            complexity_indicators = 0
            
            for line in non_empty_lines:
                line_lower = line.lower().strip()
                
                # Control structures
                if any(keyword in line_lower for keyword in [
                    'if ', 'elif ', 'else:', 'for ', 'while ', 'try:', 'except:', 
                    'switch', 'case', 'catch', 'finally'
                ]):
                    complexity_indicators += 1
                
                # Function/class definitions
                if any(keyword in line_lower for keyword in [
                    'def ', 'class ', 'function ', 'async def', 'public ', 'private '
                ]):
                    complexity_indicators += 2
                
                # Complex patterns
                if any(pattern in line_lower for pattern in [
                    'lambda', '=>', 'async', 'await', 'yield', 'recursive'
                ]):
                    complexity_indicators += 1
            
            # Normalize to 0-1 scale
            if not non_empty_lines:
                return 0.0
            
            complexity_ratio = complexity_indicators / len(non_empty_lines)
            return min(1.0, complexity_ratio * 2)  # Scale up for visibility
            
        except Exception:
            return 0.5  # Default medium complexity

    def _calculate_priority_score(self, file_path: str, size_bytes: int, complexity: float) -> float:
        """Calculate overall priority score for a file"""
        # Base priority from path patterns
        base_priority = 0.5
        path_lower = file_path.lower()
        
        for priority_level, patterns in self.priority_patterns.items():
            for pattern in patterns:
                if fnmatch.fnmatch(path_lower, pattern.lower()):
                    base_priority = {
                        'critical': 1.0,
                        'high': 0.8,
                        'medium': 0.6,
                        'low': 0.4,
                        'minimal': 0.2
                    }.get(priority_level, 0.5)
                    break
        
        # Adjust for size (larger files often more important, but too large is unwieldy)
        size_factor = 1.0
        if size_bytes > 100000:  # > 100KB
            size_factor = 0.8  # Slightly reduce priority for very large files
        elif size_bytes > 10000:  # > 10KB
            size_factor = 1.1  # Boost medium-sized files
        elif size_bytes < 1000:  # < 1KB
            size_factor = 0.9  # Slightly reduce very small files
        
        # Adjust for complexity (more complex = higher priority)
        complexity_factor = 0.7 + (complexity * 0.6)  # 0.7 to 1.3 range
        
        final_priority = base_priority * size_factor * complexity_factor
        return min(1.0, final_priority)

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get current performance statistics"""
        cache_size = len(self.file_cache)
        avg_analysis_time = 0.0
        
        if self.file_cache:
            avg_analysis_time = sum(f.analysis_time_ms for f in self.file_cache.values()) / cache_size
        
        return {
            "cached_files": cache_size,
            "average_analysis_time_ms": avg_analysis_time,
            "max_workers": self.max_workers,
            "memory_limit_mb": self.max_memory_mb,
            "cache_hit_rate": "N/A"  # Could implement if needed
        }

    async def cleanup_cache(self, max_age_hours: int = 24):
        """Clean up old cache entries to manage memory"""
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        expired_keys = []
        for key, metrics in self.file_cache.items():
            if current_time - metrics.last_modified > max_age_seconds:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.file_cache[key]
        
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")