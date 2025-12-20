# backend/api/comprehensive_review.py
"""
Comprehensive Advanced Code Review API Endpoint
Provides deep, multi-layered AI analysis including security, performance, and architecture insights
"""
from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import JSONResponse
import logging
from typing import Optional
from pathlib import Path

from backend.services.review_service import RealReviewService
from backend.models.review import ReviewEntry

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/review/comprehensive")
async def comprehensive_analysis(
    workspace_root: Optional[str] = Query(None, description="Repository root path"),
    analysis_depth: str = Query("comprehensive", description="Analysis depth: quick, standard, comprehensive, deep")
):
    """
    Perform comprehensive AI-powered code analysis of working tree changes
    
    This provides deep, multi-layered analysis including:
    - Security vulnerability scanning with CWE mapping
    - Performance optimization opportunities  
    - Architecture pattern analysis
    - Technical debt assessment
    - Code quality scoring
    - Executive summary with recommendations
    
    Args:
        workspace_root: Path to git repository root (defaults to current directory)
        analysis_depth: Level of analysis detail (quick/standard/comprehensive/deep)
    
    Returns:
        ComprehensiveAnalysis object with all analysis results and scores
    """
    
    try:
        # Get workspace root - fallback to current directory
        repo_path = workspace_root or str(Path.cwd())
        
        # Validate that it's a git repository
        try:
            review_service = RealReviewService(repo_path, analysis_depth=analysis_depth)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
            
        logger.info(f"Starting comprehensive analysis for {repo_path} with {analysis_depth} depth")
        
        # Perform comprehensive analysis
        analysis = await review_service.analyze_working_tree_comprehensive()
        
        logger.info(f"Comprehensive analysis complete - analyzed {analysis.files_analyzed} files")
        
        # Convert dataclass to dict for JSON response
        from dataclasses import asdict
        result = asdict(analysis)
        
        return JSONResponse(
            content={
                "success": True,
                "analysis": result,
                "message": f"Comprehensive analysis complete - {analysis.files_analyzed} files analyzed"
            }
        )
        
    except Exception as e:
        logger.error(f"Comprehensive analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/review/comprehensive/stream")
async def comprehensive_analysis_stream(
    request: Request,
    workspace_root: Optional[str] = Query(None, description="Repository root path"),
    analysis_depth: str = Query("comprehensive", description="Analysis depth: quick, standard, comprehensive, deep")
):
    """
    Stream comprehensive analysis with real-time progress updates
    
    Provides the same deep analysis as /comprehensive but with streaming progress updates
    for better user experience during long analyses.
    """
    from fastapi.responses import StreamingResponse
    import json
    import asyncio
    
    async def event_stream():
        try:
            # Get workspace root - fallback to current directory
            repo_path = workspace_root or str(Path.cwd())
            
            # Validate that it's a git repository
            try:
                review_service = RealReviewService(repo_path, analysis_depth=analysis_depth)
            except ValueError as e:
                yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
                return
                
            # Start analysis with progress updates
            yield f"event: live-progress\ndata: Starting {analysis_depth} analysis of working tree…\n\n"
            
            # Get repository context
            yield f"event: live-progress\ndata: Analyzing repository structure and context…\n\n"
            repo_context = await review_service.analyze_repository_context()
            
            # Get changes
            changes = review_service.repo_service.get_working_tree_changes()
            
            if not changes:
                yield f"event: live-progress\ndata: No changes detected in working tree\n\n"
                yield f"event: done\ndata: Analysis complete - no changes found\n\n"
                return
                
            yield f"event: live-progress\ndata: Found {len(changes)} changed files for analysis\n\n"
            yield f"event: live-progress\ndata: Beginning comprehensive file analysis…\n\n"
            
            # Collect all analysis results
            file_analyses = []
            review_entries = []
            all_security_findings = []
            all_performance_issues = []
            all_technical_debt = []
            
            # Process each file with progress
            for i, change in enumerate(changes[:review_service.config["max_files"]], 1):
                file_path = change["path"]
                
                yield f"event: live-progress\ndata: Analyzing {file_path}… ({i}/{min(len(changes), review_service.config['max_files'])})\n\n"
                
                try:
                    # Comprehensive file analysis
                    file_analysis = await review_service.analyze_file_change_comprehensive(change)
                    file_analyses.append(file_analysis)
                    
                    # Extract and emit results
                    results = file_analysis["analysis_results"]
                    
                    if "basic" in results:
                        review_entries.append(results["basic"])
                        
                        # Send immediate file result
                        file_result = {
                            'file': file_path,
                            'issues_found': len(results["basic"].issues),
                            'security_findings': len(results.get("security", [])),
                            'performance_issues': len(results.get("performance", [])),
                            'tech_debt_items': len(results.get("tech_debt", []))
                        }
                        yield f"event: file-complete\ndata: {json.dumps(file_result)}\n\n"
                    
                    # Collect findings
                    if "security" in results:
                        all_security_findings.extend(results["security"])
                    if "performance" in results:
                        all_performance_issues.extend(results["performance"])
                    if "tech_debt" in results:
                        all_technical_debt.extend(results["tech_debt"])
                        
                except Exception as e:
                    logger.error(f"Failed comprehensive analysis of {file_path}: {e}")
                    yield f"event: error\ndata: {json.dumps({'error': f'Failed to analyze {file_path}: {str(e)}'})}\n\n"
                
                # Small delay for streaming effect
                await asyncio.sleep(0.1)
            
            # Cross-file architecture analysis
            if len(file_analyses) > 1 and review_service.config.get("enable_architecture_analysis", False):
                yield f"event: live-progress\ndata: Analyzing cross-file architecture patterns…\n\n"
                architecture_insights = await review_service._analyze_architecture_patterns(file_analyses, repo_context)
            else:
                architecture_insights = []
            
            # Calculate scores
            yield f"event: live-progress\ndata: Calculating quality scores and generating summary…\n\n"
            scores = review_service._calculate_quality_scores(
                review_entries, all_security_findings, all_performance_issues, all_technical_debt
            )
            
            # Generate executive summary
            executive_summary, recommendations = await review_service._generate_executive_summary(
                review_entries, all_security_findings, all_performance_issues, 
                all_technical_debt, architecture_insights, scores
            )
            
            # Send final comprehensive results
            from datetime import datetime
            
            final_analysis = {
                "timestamp": datetime.now().isoformat(),
                "repository_path": str(review_service.repo_path),
                "files_analyzed": len(file_analyses),
                "total_issues": len([issue for entry in review_entries for issue in entry.issues]),
                
                "review_entries": [
                    {
                        "file": entry.file,
                        "diff": entry.diff,
                        "issues": [
                            {
                                "id": issue.id,
                                "title": issue.title,
                                "message": issue.message,
                                "severity": issue.severity,
                                "line_number": issue.line_number,
                                "suggestion": issue.suggestion
                            } for issue in entry.issues
                        ],
                        "summary": entry.summary,
                        "status": entry.status
                    } for entry in review_entries
                ],
                "security_findings": all_security_findings,
                "performance_issues": all_performance_issues,
                "architecture_insights": [
                    {
                        "pattern_type": insight.pattern_type,
                        "title": insight.title,
                        "description": insight.description,
                        "impact": insight.impact,
                        "recommendation": insight.recommendation,
                        "files_affected": insight.files_affected
                    } for insight in architecture_insights
                ] if architecture_insights else [],
                "technical_debt": all_technical_debt,
                
                "security_score": scores["security"],
                "performance_score": scores["performance"], 
                "maintainability_score": scores["maintainability"],
                "overall_quality_score": scores["overall"],
                
                "executive_summary": executive_summary,
                "recommendations": recommendations
            }
            
            yield f"event: comprehensive-complete\ndata: {json.dumps(final_analysis)}\n\n"
            yield f"event: done\ndata: Comprehensive analysis complete - {len(file_analyses)} files analyzed\n\n"
            
        except Exception as e:
            logger.error(f"Comprehensive analysis stream failed: {e}")
            yield f"event: error\ndata: {json.dumps({'error': f'Analysis failed: {str(e)}'})}\n\n"
    
    return StreamingResponse(
        event_stream(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Headers": "*",
        }
    )


@router.get("/review/repository-summary")
async def get_repository_summary(
    workspace_root: Optional[str] = Query(None, description="Repository root path")
):
    """
    Get summary information about the repository without performing full analysis
    
    Returns basic statistics about the repository state and pending changes
    """
    try:
        # Get workspace root - fallback to current directory  
        repo_path = workspace_root or str(Path.cwd())
        
        # Create service instance
        try:
            review_service = RealReviewService(repo_path)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        
        # Get repository summary
        summary = review_service.get_repository_summary()
        
        return JSONResponse(content={
            "success": True,
            "repository_summary": summary
        })
        
    except Exception as e:
        logger.error(f"Repository summary failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get repository summary: {str(e)}")