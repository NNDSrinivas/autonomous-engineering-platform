#!/usr/bin/env python3
"""
Automated PR monitoring and fixing script.
Monitors PR #54 for build failures and new comments, automatically fixes issues.
"""

import subprocess
import time
import json
import sys
import requests
from datetime import datetime

def run_command(cmd, capture_output=True):
    """Run a shell command and return result."""
    try:
        result = subprocess.run(
            cmd, 
            shell=True, 
            capture_output=capture_output, 
            text=True, 
            cwd="/Users/mounikakapa/Desktop/Personal Projects/autonomous-engineering-platform"
        )
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def check_pr_status():
    """Check the current status of PR #54."""
    success, output, error = run_command("gh pr view 54 --json checks,state,reviews")
    if not success:
        print(f"Failed to check PR status: {error}")
        return None
    
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        print(f"Failed to parse PR status: {output}")
        return None

def check_failing_builds():
    """Check for failing CI builds."""
    success, output, error = run_command("gh pr checks 54 --json name,status,conclusion")
    if not success:
        print(f"Failed to check builds: {error}")
        return []
    
    try:
        checks = json.loads(output)
        failing = []
        for check in checks:
            if check.get('conclusion') == 'failure' or check.get('status') == 'failed':
                failing.append(check['name'])
        return failing
    except json.JSONDecodeError:
        print(f"Failed to parse build status: {output}")
        return []

def get_new_comments():
    """Get new comments on the PR."""
    success, output, error = run_command("gh pr view 54 --comments --json comments")
    if not success:
        print(f"Failed to get comments: {error}")
        return []
    
    try:
        data = json.loads(output)
        # Filter for comments from the last 5 minutes
        recent_comments = []
        for comment in data.get('comments', []):
            # This is a simplified check - in real implementation, 
            # you'd parse the timestamp and check recency
            if 'CodeQL' in comment.get('body', '') or 'failed' in comment.get('body', '').lower():
                recent_comments.append(comment)
        return recent_comments
    except json.JSONDecodeError:
        print(f"Failed to parse comments: {output}")
        return []

def fix_linting_issues():
    """Fix common linting issues."""
    print("Fixing linting issues...")
    
    # Run ruff with fixes
    success, output, error = run_command("ruff check backend/ tests/ *.py --fix")
    if not success:
        print(f"Ruff failed: {error}")
    
    # Run black formatting
    success, output, error = run_command("black .")
    if not success:
        print(f"Black failed: {error}")
    
    return True

def check_and_fix_security_issues():
    """Check for new security issues and fix them."""
    print("Checking for security issues...")
    
    # Get CodeQL alerts
    success, output, error = run_command(
        "gh api repos/NNDSrinivas/autonomous-engineering-platform/code-scanning/alerts --jq '.[0:10] | .[] | {rule_id: .rule.id, severity: .rule.severity, path: .most_recent_instance.location.path, line: .most_recent_instance.location.start_line, message: .most_recent_instance.message.text}'"
    )
    
    if success and output.strip():
        print("Found security issues:")
        print(output)
        # Here you would implement specific fixes based on the issues found
        return False  # Indicates issues found
    
    return True  # No issues found

def commit_and_push_fixes():
    """Commit and push any fixes made."""
    print("Checking for changes to commit...")
    
    success, output, error = run_command("git diff --name-only")
    if not success:
        return False
    
    if output.strip():
        print("Found changes, committing...")
        run_command("git add .")
        run_command('git commit -m "fix: Automated fixes for CI and security issues"')
        success, output, error = run_command("git push origin feature/navi-execution-controls")
        if success:
            print("Pushed fixes successfully")
            return True
        else:
            print(f"Failed to push: {error}")
            return False
    
    print("No changes to commit")
    return True

def monitor_pr():
    """Main monitoring loop."""
    print(f"Starting PR monitoring at {datetime.now()}")
    
    max_iterations = 20  # Monitor for about 1 hour (20 * 3 minutes)
    iteration = 0
    
    while iteration < max_iterations:
        print(f"\n--- Iteration {iteration + 1}/{max_iterations} at {datetime.now()} ---")
        
        # Check PR status
        pr_status = check_pr_status()
        if not pr_status:
            print("Could not get PR status, skipping this iteration")
            time.sleep(180)  # Wait 3 minutes
            iteration += 1
            continue
        
        print(f"PR State: {pr_status.get('state', 'unknown')}")
        
        # Check for failing builds
        failing_builds = check_failing_builds()
        if failing_builds:
            print(f"Found failing builds: {failing_builds}")
            
            # Try to fix common issues
            fix_linting_issues()
            
            # Check and fix security issues
            security_clean = check_and_fix_security_issues()
            if not security_clean:
                print("Security issues found - manual review may be needed")
            
            # Commit and push fixes
            if commit_and_push_fixes():
                print("Applied fixes, waiting for CI to re-run...")
                time.sleep(300)  # Wait 5 minutes for CI to start
            else:
                print("No fixes applied or push failed")
        else:
            print("No failing builds found")
        
        # Check for new comments
        new_comments = get_new_comments()
        if new_comments:
            print(f"Found {len(new_comments)} recent comments")
            for comment in new_comments:
                print(f"Comment: {comment.get('body', '')[:100]}...")
        
        # Check if all checks are passing
        pr_status = check_pr_status()
        if pr_status:
            checks = pr_status.get('checks', [])
            all_passing = all(
                check.get('conclusion') == 'success' 
                for check in checks 
                if check.get('conclusion') is not None
            )
            
            if all_passing and checks:
                print("All checks are passing! PR is ready for review.")
                break
        
        print("Waiting 3 minutes before next check...")
        time.sleep(180)  # Wait 3 minutes
        iteration += 1
    
    print(f"\nMonitoring completed at {datetime.now()}")
    print("Final PR status check...")
    
    # Final status check
    failing_builds = check_failing_builds()
    if not failing_builds:
        print("SUCCESS: No failing builds detected!")
        print("PR is ready for manual review.")
    else:
        print(f"ATTENTION: Still have failing builds: {failing_builds}")
        print("Manual intervention may be required.")

if __name__ == "__main__":
    monitor_pr()