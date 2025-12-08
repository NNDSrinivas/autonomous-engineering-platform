"""
Workflow Steps

All 10 actionable steps of the autonomous engineering workflow.
Each step performs a specific action and returns results for user approval or continuation.
"""

import logging
from typing import Dict, Any, Optional

from backend.agent.jira_engine.planner import generate_jira_plan
from backend.agent.tools.search_repo import search_repo
from backend.agent.tools.read_file import read_file
from backend.agent.tools.apply_diff import apply_diff
from backend.agent.tools.run_command import run_command
from backend.agent.tools.github_tools import github_create_pr
from backend.agent.jira_engine.executor import transition_jira, add_jira_comment
from backend.llm.router import complete_chat as call_llm

logger = logging.getLogger(__name__)


# ==============================================================================
# STEP 1: ANALYSIS
# ==============================================================================

async def step_analysis(
    state: Any,
    issue: Dict[str, Any],
    enriched_context: Dict[str, Any],
    workspace_context: Optional[str] = None
) -> Dict[str, Any]:
    """
    Analyze Jira task and generate comprehensive execution plan.
    
    Args:
        state: WorkflowState instance
        issue: Parsed Jira issue
        enriched_context: Enriched organizational context
        workspace_context: Optional workspace/codebase context
        
    Returns:
        Dict with message, plan, and next actions
    """
    try:
        logger.info(f"Step 1: Analyzing {issue.get('id')}")
        
        # Generate comprehensive plan
        plan = await generate_jira_plan(issue, enriched_context, workspace_context)
        
        # Store in state
        state.issue = issue
        state.enriched_context = enriched_context
        state.plan = plan
        
        # Format plan for display
        plan_summary = f"""📘 **Analysis Complete**

**Task**: {issue.get('title')}

**Summary**: {plan.get('summary', 'No summary available')}

**Acceptance Criteria**:
{chr(10).join(['- ' + c for c in plan.get('acceptance_criteria', [])])}

**Next Steps**:
{chr(10).join(['1. ' + s for s in plan.get('next_steps', [])[:3]])}

Ready to proceed with implementation?
"""
        
        return {
            "success": True,
            "message": plan_summary,
            "data": {"plan": plan},
            "actions": ["continue", "modify plan", "cancel"]
        }
        
    except Exception as e:
        logger.error(f"Error in step_analysis: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"❌ Analysis failed: {str(e)}",
            "error": str(e),
            "actions": ["retry", "cancel"]
        }


# ==============================================================================
# STEP 2: LOCATE FILES
# ==============================================================================

async def step_locate_files(
    state: Any,
    user_id: str,
    workspace_root: str
) -> Dict[str, Any]:
    """
    Find relevant code files for implementing the task.
    
    Args:
        state: WorkflowState instance
        user_id: User ID
        workspace_root: Workspace root directory
        
    Returns:
        Dict with matched files and next actions
    """
    try:
        logger.info(f"Step 2: Locating files for {state.issue_id}")
        
        # Build search query from issue and plan
        issue_title = state.issue.get("title", "")
        state.plan.get("summary", "")
        
        # Search for relevant files
        search_result = await search_repo(
            user_id=user_id,
            query=issue_title,
            workspace_root=workspace_root,
            max_results=20,
            case_sensitive=False,
            regex=False
        )
        
        if not search_result.get("success"):
            return {
                "success": False,
                "message": f"❌ File search failed: {search_result.get('error')}",
                "actions": ["retry", "skip", "cancel"]
            }
        
        matches = search_result.get("matches", [])
        file_list = list(set([m["file"] for m in matches]))  # Unique files
        
        # Store in state
        state.file_targets = file_list[:10]  # Limit to top 10
        
        file_summary = f"""📂 **Relevant Files Found**

Found {len(file_list)} file(s) that may need changes:

{chr(10).join(['- ' + f for f in state.file_targets])}

Ready to propose code changes?
"""
        
        return {
            "success": True,
            "message": file_summary,
            "data": {"files": state.file_targets},
            "actions": ["continue", "add more files", "cancel"]
        }
        
    except Exception as e:
        logger.error(f"Error in step_locate_files: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"❌ File location failed: {str(e)}",
            "error": str(e),
            "actions": ["retry", "cancel"]
        }


# ==============================================================================
# STEP 3: PROPOSE DIFFS
# ==============================================================================

async def step_propose_diffs(state: Any, user_id: str) -> Dict[str, Any]:
    """
    Generate proposed code changes (unified diffs) for target files.
    
    Args:
        state: WorkflowState instance
        user_id: User ID
        
    Returns:
        Dict with proposed diffs and approval actions
    """
    try:
        logger.info(f"Step 3: Proposing diffs for {state.issue_id}")
        
        diffs = []
        
        for file_path in state.file_targets:
            # Read current file content
            read_result = await read_file(user_id=user_id, path=file_path)
            
            if not read_result.get("success"):
                logger.warning(f"Could not read {file_path}: {read_result.get('error')}")
                continue
            
            current_content = read_result.get("content", "")
            
            # Generate diff using LLM
            diff_prompt = f"""Generate a unified diff to implement this change:

**Task**: {state.issue.get('title')}
**Plan**: {state.plan.get('summary', '')}
**File**: {file_path}

**Current content**:
```
{current_content[:2000]}
```

Generate a unified diff that implements the required changes.
Use proper unified diff format starting with --- and +++.
"""
            
            try:
                system_msg = "You are a code modification assistant. Generate precise unified diffs."
                llm_response = call_llm(
                    system=system_msg,
                    user=diff_prompt,
                    model="gpt-4o",
                    temperature=0.2
                )
                
                diff_text = llm_response  # complete_chat returns string directly
                
                diffs.append({
                    "file": file_path,
                    "diff": diff_text,
                    "current_content": current_content
                })
                
            except Exception as e:
                logger.error(f"Error generating diff for {file_path}: {e}")
                continue
        
        # Store in state
        state.diff_proposals = diffs
        
        diff_summary = f"""📝 **Proposed Changes**

Generated {len(diffs)} diff(s) for review:

{chr(10).join([f"- {d['file']}" for d in diffs])}

**Review and approve** each diff before applying changes.
"""
        
        return {
            "success": True,
            "message": diff_summary,
            "data": {"diffs": diffs},
            "actions": ["approve all", "review individually", "cancel"]
        }
        
    except Exception as e:
        logger.error(f"Error in step_propose_diffs: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"❌ Diff generation failed: {str(e)}",
            "error": str(e),
            "actions": ["retry", "cancel"]
        }


# ==============================================================================
# STEP 4: APPLY DIFFS
# ==============================================================================

async def step_apply_diffs(state: Any, user_id: str) -> Dict[str, Any]:
    """
    Apply approved code changes to files.
    
    Args:
        state: WorkflowState instance
        user_id: User ID
        
    Returns:
        Dict with application results
    """
    try:
        logger.info(f"Step 4: Applying diffs for {state.issue_id}")
        
        applied = []
        failed = []
        
        for diff_item in state.diff_proposals:
            file_path = diff_item["file"]
            diff_text = diff_item["diff"]
            old_content = diff_item["current_content"]
            
            # Apply diff
            result = await apply_diff(
                user_id=user_id,
                path=file_path,
                diff=diff_text,
                old_content=old_content
            )
            
            if result.get("success"):
                applied.append(file_path)
            else:
                failed.append({"file": file_path, "error": result.get("error")})
        
        if failed:
            fail_summary = "\n".join([f"- {f['file']}: {f['error']}" for f in failed])
            return {
                "success": False,
                "message": f"⚠️ Some diffs failed to apply:\n{fail_summary}",
                "data": {"applied": applied, "failed": failed},
                "actions": ["continue anyway", "retry failed", "cancel"]
            }
        
        return {
            "success": True,
            "message": f"🧩 **Code Updated**\n\nSuccessfully applied changes to {len(applied)} file(s).\n\nReady to run tests?",
            "data": {"applied": applied},
            "actions": ["continue", "cancel"]
        }
        
    except Exception as e:
        logger.error(f"Error in step_apply_diffs: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"❌ Diff application failed: {str(e)}",
            "error": str(e),
            "actions": ["retry", "cancel"]
        }


# ==============================================================================
# STEP 5: RUN TESTS
# ==============================================================================

async def step_run_tests(state: Any, user_id: str, cwd: str) -> Dict[str, Any]:
    """
    Execute test suite to validate changes.
    
    Args:
        state: WorkflowState instance
        user_id: User ID
        cwd: Working directory
        
    Returns:
        Dict with test results
    """
    try:
        logger.info(f"Step 5: Running tests for {state.issue_id}")
        
        # Run pytest
        test_result = await run_command(
            user_id=user_id,
            command="pytest -q --tb=short",
            cwd=cwd,
            timeout=120
        )
        
        state.test_results = test_result
        
        stdout = test_result.get("stdout", "")
        stderr = test_result.get("stderr", "")
        exit_code = test_result.get("exit_code", 1)
        
        if exit_code == 0:
            return {
                "success": True,
                "message": f"✅ **All Tests Passed**\n\n```\n{stdout[:500]}\n```\n\nReady to commit changes?",
                "data": {"test_results": test_result},
                "actions": ["continue", "cancel"]
            }
        else:
            return {
                "success": False,
                "message": f"❌ **Tests Failed**\n\n```\n{stderr[:500]}\n```\n\nWhat would you like to do?",
                "data": {"test_results": test_result},
                "actions": ["fix tests", "continue anyway", "cancel"]
            }
        
    except Exception as e:
        logger.error(f"Error in step_run_tests: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"❌ Test execution failed: {str(e)}",
            "error": str(e),
            "actions": ["retry", "skip tests", "cancel"]
        }


# ==============================================================================
# STEP 6: COMMIT CHANGES
# ==============================================================================

async def step_commit_changes(state: Any, user_id: str, cwd: str) -> Dict[str, Any]:
    """
    Commit changes to git.
    
    Args:
        state: WorkflowState instance
        user_id: User ID
        cwd: Working directory
        
    Returns:
        Dict with commit result
    """
    try:
        logger.info(f"Step 6: Committing changes for {state.issue_id}")
        
        # Stage all changes
        await run_command(user_id=user_id, command="git add .", cwd=cwd)
        
        # Generate commit message
        commit_msg = f"feat: Implement {state.issue_id}\n\n{state.issue.get('title')}\n\nAutonomously implemented by NAVI"
        
        # Commit
        commit_result = await run_command(
            user_id=user_id,
            command=f'git commit -m "{commit_msg}"',
            cwd=cwd
        )
        
        if commit_result.get("success"):
            return {
                "success": True,
                "message": f"💾 **Changes Committed**\n\n```\n{commit_result.get('stdout', '')}\n```\n\nReady to push branch?",
                "data": {"commit": commit_result},
                "actions": ["continue", "cancel"]
            }
        else:
            return {
                "success": False,
                "message": f"❌ Commit failed: {commit_result.get('error')}",
                "data": {"commit": commit_result},
                "actions": ["retry", "cancel"]
            }
        
    except Exception as e:
        logger.error(f"Error in step_commit_changes: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"❌ Commit failed: {str(e)}",
            "error": str(e),
            "actions": ["retry", "cancel"]
        }


# ==============================================================================
# STEP 7: PUSH BRANCH
# ==============================================================================

async def step_push_branch(state: Any, user_id: str, cwd: str) -> Dict[str, Any]:
    """
    Push branch to remote repository.
    
    Args:
        state: WorkflowState instance
        user_id: User ID
        cwd: Working directory
        
    Returns:
        Dict with push result
    """
    try:
        logger.info(f"Step 7: Pushing branch for {state.issue_id}")
        
        # Generate branch name
        branch_name = f"navi/{state.issue_id.lower().replace('_', '-')}"
        state.branch_name = branch_name
        
        # Create and checkout branch
        await run_command(user_id=user_id, command=f"git checkout -b {branch_name}", cwd=cwd)
        
        # Push branch
        push_result = await run_command(
            user_id=user_id,
            command=f"git push -u origin {branch_name}",
            cwd=cwd
        )
        
        if push_result.get("success"):
            return {
                "success": True,
                "message": f"⬆️ **Branch Pushed**\n\nBranch `{branch_name}` pushed to remote.\n\nReady to create pull request?",
                "data": {"branch": branch_name, "push": push_result},
                "actions": ["continue", "cancel"]
            }
        else:
            return {
                "success": False,
                "message": f"❌ Push failed: {push_result.get('error')}",
                "data": {"push": push_result},
                "actions": ["retry", "cancel"]
            }
        
    except Exception as e:
        logger.error(f"Error in step_push_branch: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"❌ Push failed: {str(e)}",
            "error": str(e),
            "actions": ["retry", "cancel"]
        }


# ==============================================================================
# STEP 8: CREATE PR
# ==============================================================================

async def step_create_pr(state: Any, user_id: str) -> Dict[str, Any]:
    """
    Create pull request on GitHub.
    
    Args:
        state: WorkflowState instance
        user_id: User ID
        
    Returns:
        Dict with PR creation result
    """
    try:
        logger.info(f"Step 8: Creating PR for {state.issue_id}")
        
        # Generate PR title and body
        pr_title = f"[{state.issue_id}] {state.issue.get('title')}"
        pr_body = f"""## {state.issue_id}: {state.issue.get('title')}

### Summary
{state.plan.get('summary', '')}

### Changes
{chr(10).join(['- Modified: ' + f for f in state.file_targets])}

### Acceptance Criteria
{chr(10).join(['- [ ] ' + c for c in state.plan.get('acceptance_criteria', [])])}

---
*Autonomously implemented by NAVI*
"""
        
        # Create PR
        pr_result = await github_create_pr(
            user_id=user_id,
            branch=state.branch_name,
            title=pr_title,
            body=pr_body,
            base_branch="main"
        )
        
        if pr_result.get("success"):
            state.pr_url = pr_result.get("pr_url")
            state.pr_number = pr_result.get("pr_number")
            
            return {
                "success": True,
                "message": f"🔀 **Pull Request Created**\n\nPR #{pr_result.get('pr_number')}: {pr_result.get('pr_url')}\n\nReady to update Jira?",
                "data": {"pr": pr_result},
                "actions": ["continue", "cancel"]
            }
        else:
            return {
                "success": False,
                "message": f"❌ PR creation failed: {pr_result.get('error')}",
                "data": {"pr": pr_result},
                "actions": ["retry", "cancel"]
            }
        
    except Exception as e:
        logger.error(f"Error in step_create_pr: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"❌ PR creation failed: {str(e)}",
            "error": str(e),
            "actions": ["retry", "cancel"]
        }


# ==============================================================================
# STEP 9: UPDATE JIRA
# ==============================================================================

async def step_update_jira(state: Any, user_id: str) -> Dict[str, Any]:
    """
    Update Jira issue status and add comment with PR link.
    
    Args:
        state: WorkflowState instance
        user_id: User ID
        
    Returns:
        Dict with Jira update result
    """
    try:
        logger.info(f"Step 9: Updating Jira {state.issue_id}")
        
        # Add comment with PR link
        comment = f"""✅ Implementation complete!

**Pull Request**: {state.pr_url}
**Branch**: {state.branch_name}

Autonomously implemented by NAVI. Ready for code review.
"""
        
        await add_jira_comment(user_id=user_id, issue_id=state.issue_id, comment=comment)
        
        # Transition to Code Review
        transition_result = await transition_jira(
            user_id=user_id,
            issue_id=state.issue_id,
            target_status="Code Review"
        )
        
        if transition_result.get("success"):
            return {
                "success": True,
                "message": f"📌 **Jira Updated**\n\n{state.issue_id} moved to Code Review.\n\nWorkflow complete!",
                "data": {"transition": transition_result},
                "actions": ["finish"]
            }
        else:
            return {
                "success": False,
                "message": f"⚠️ Jira update failed: {transition_result.get('error')}\n\nBut PR was created successfully.",
                "data": {"transition": transition_result},
                "actions": ["finish anyway", "retry"]
            }
        
    except Exception as e:
        logger.error(f"Error in step_update_jira: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"❌ Jira update failed: {str(e)}",
            "error": str(e),
            "actions": ["retry", "finish anyway"]
        }


# ==============================================================================
# STEP 10: DONE
# ==============================================================================

async def step_done(state: Any) -> Dict[str, Any]:
    """
    Mark workflow as complete.
    
    Args:
        state: WorkflowState instance
        
    Returns:
        Dict with completion message
    """
    try:
        logger.info(f"Step 10: Workflow complete for {state.issue_id}")
        
        state.complete()
        
        summary = f"""🎉 **Autonomous Workflow Complete!**

**Task**: {state.issue.get('title')}
**Jira**: {state.issue_id}
**Branch**: {state.branch_name}
**PR**: {state.pr_url}

**Steps Completed**:
✅ Analysis and planning
✅ File identification
✅ Code changes proposed and applied
✅ Tests executed
✅ Changes committed
✅ Branch pushed
✅ Pull request created
✅ Jira updated

Ready to work on another task?
"""
        
        return {
            "success": True,
            "message": summary,
            "data": {"workflow": state.to_dict()},
            "actions": []
        }
        
    except Exception as e:
        logger.error(f"Error in step_done: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Workflow completed with warnings: {str(e)}",
            "error": str(e),
            "actions": []
        }
