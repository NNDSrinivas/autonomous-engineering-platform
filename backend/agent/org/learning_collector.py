"""
Learning Collector - Organizational Signal Processing

Collects and structures organizational signals from PR events, CI failures, deployments,
incidents and other engineering activities for learning and improvement insights.
"""

import logging
from datetime import datetime
from typing import Dict, List, Any

from .org_memory_store import OrgSignal, SignalType

logger = logging.getLogger(__name__)


class LearningCollector:
    """
    Collects organizational signals from various engineering events.
    
    Transforms raw event data into structured organizational signals that can be
    used for learning, pattern detection, and organizational improvement insights.
    """
    
    def collect_from_pr_event(self, pr_data: Dict[str, Any]) -> OrgSignal:
        """
        Collect signal from PR events
        
        Args:
            pr_data: PR event data from webhooks or API
            
        Returns:
            Organizational signal
        """
        # Extract PR action
        action = pr_data.get('action', 'unknown')
        pr = pr_data.get('pull_request', {})
        
        # Determine signal type based on PR action
        if action in ['closed', 'merged'] and pr.get('merged', False):
            signal_type = SignalType.PR_APPROVAL
        elif action == 'closed' and not pr.get('merged', False):
            signal_type = SignalType.PR_REJECTION
        else:
            signal_type = SignalType.PR_COMMENT
        
        # Extract repository info
        repo_name = pr_data.get('repository', {}).get('name', '')
        repo_full_name = pr_data.get('repository', {}).get('full_name', '')
        org_name = repo_full_name.split('/')[0] if '/' in repo_full_name else ''
        
        # Extract PR context
        files = []
        if 'files' in pr_data:
            files = [f.get('filename', '') for f in pr_data['files']]
        
        # Extract author info
        author = pr.get('user', {}).get('login', '')
        
        # Assess severity and impact
        severity = self._assess_pr_severity(pr, files)
        impact_scope = self._assess_pr_impact(files, pr)
        
        # Extract cause for rejections
        cause = None
        if signal_type == SignalType.PR_REJECTION:
            cause = f"PR rejected: {pr.get('title', '')[:200]}"
        
        signal = OrgSignal(
            signal_type=signal_type,
            repo=repo_name,
            org=org_name,
            files=files,
            cause=cause,
            author=author,
            severity=severity,
            impact_scope=impact_scope,
            timestamp=datetime.now(),
            metadata={
                'pr_number': pr.get('number'),
                'pr_url': pr.get('html_url'),
                'additions': pr.get('additions', 0),
                'deletions': pr.get('deletions', 0),
                'commits': pr.get('commits', 0),
                'review_comments': pr.get('review_comments', 0),
                'base_branch': pr.get('base', {}).get('ref'),
                'head_branch': pr.get('head', {}).get('ref')
            },
            tags=[f"pr:{action}"]
        )
        
        logger.info(f"Collected PR signal: {signal_type.value} for {repo_name} by {author}")
        return signal
    
    def collect_from_ci_event(self, ci_data: Dict[str, Any]) -> OrgSignal:
        """
        Collect signal from CI events
        
        Args:
            ci_data: CI event data
            
        Returns:
            Organizational signal
        """
        status = ci_data.get('conclusion', ci_data.get('status', 'unknown')).lower()
        
        # Determine signal type based on status
        if status in ['success', 'completed']:
            signal_type = SignalType.CI_SUCCESS
        else:
            signal_type = SignalType.CI_FAILURE
        
        # Extract repository info
        repo_full_name = ci_data.get('repository', {}).get('full_name', '')
        org_name = repo_full_name.split('/')[0] if '/' in repo_full_name else ''
        repo_name = repo_full_name.split('/')[-1] if '/' in repo_full_name else repo_full_name
        
        # Extract author info
        author = ci_data.get('head_commit', {}).get('author', {}).get('name', '')
        if not author:
            author = ci_data.get('sender', {}).get('login', '')
        
        # Extract files (if available)
        files = []
        if 'head_commit' in ci_data and 'modified' in ci_data['head_commit']:
            files = ci_data['head_commit']['modified']
        
        # Extract failure reason from various CI systems
        cause = None
        if signal_type == SignalType.CI_FAILURE:
            if 'workflow_run' in ci_data:
                cause = f"Workflow '{ci_data['workflow_run'].get('name', 'unknown')}' failed"
            elif 'check_run' in ci_data:
                cause = f"Check '{ci_data['check_run'].get('name', 'unknown')}' failed"
            elif 'message' in ci_data:
                cause = ci_data['message'][:200]
            else:
                cause = "CI pipeline failed"
        
        # Assess severity
        severity = "MEDIUM"  # Default
        if signal_type == SignalType.CI_FAILURE:
            if 'deploy' in str(ci_data).lower():
                severity = "HIGH"
            elif 'test' in str(ci_data).lower():
                severity = "MEDIUM"
            elif 'build' in str(ci_data).lower():
                severity = "MEDIUM"
        
        # Assess impact scope
        impact_scope = "LOCAL"
        if 'deploy' in str(ci_data).lower() or 'release' in str(ci_data).lower():
            impact_scope = "CUSTOMER"
        elif len(files) > 10:
            impact_scope = "TEAM"
        
        # Extract metadata
        metadata = {
            'workflow_name': ci_data.get('workflow_run', {}).get('name'),
            'run_id': ci_data.get('workflow_run', {}).get('id'),
            'run_url': ci_data.get('workflow_run', {}).get('html_url'),
            'run_number': ci_data.get('workflow_run', {}).get('run_number'),
            'event': ci_data.get('action'),
            'branch': ci_data.get('workflow_run', {}).get('head_branch'),
            'commit_sha': ci_data.get('workflow_run', {}).get('head_sha'),
            'duration': ci_data.get('workflow_run', {}).get('run_duration_ms'),
            'attempt': ci_data.get('workflow_run', {}).get('run_attempt', 1)
        }
        
        # Extract tags
        tags = []
        if metadata.get('workflow_name'):
            tags.append(f"workflow:{metadata['workflow_name']}")
        if metadata.get('branch'):
            tags.append(f"branch:{metadata['branch']}")
        if signal_type == SignalType.CI_FAILURE:
            tags.append("failure:ci")
        
        signal = OrgSignal(
            signal_type=signal_type,
            repo=repo_name,
            org=org_name,
            files=files,
            cause=cause,
            author=author,
            severity=severity,
            impact_scope=impact_scope,
            timestamp=datetime.now(),
            metadata=metadata,
            tags=tags
        )
        
        logger.info(f"Collected CI signal: {signal_type.value} for {repo_name} - {status}")
        return signal
    
    def _assess_pr_severity(self, pr: Dict[str, Any], files: List[str]) -> str:
        """Assess PR severity based on content and context"""
        # Check for high-risk indicators
        title = pr.get('title', '').lower()
        body = (pr.get('body') or '').lower()
        
        # Critical indicators
        critical_keywords = ['hotfix', 'critical', 'urgent', 'production', 'security']
        if any(keyword in title or keyword in body for keyword in critical_keywords):
            return "CRITICAL"
        
        # High severity indicators
        high_keywords = ['bug', 'fix', 'issue', 'problem', 'error']
        if any(keyword in title for keyword in high_keywords):
            return "HIGH"
        
        # Size-based assessment
        additions = pr.get('additions', 0)
        deletions = pr.get('deletions', 0)
        total_changes = additions + deletions
        
        if total_changes > 1000:
            return "HIGH"
        elif total_changes > 200:
            return "MEDIUM"
        else:
            return "LOW"
    
    def _assess_pr_impact(self, files: List[str], pr: Dict[str, Any]) -> str:
        """Assess PR impact scope based on files and content"""
        # Check for customer-facing changes
        customer_patterns = ['api/', 'public/', 'frontend/', 'ui/', 'web/']
        if any(any(pattern in file_path.lower() for pattern in customer_patterns) for file_path in files):
            return "CUSTOMER"
        
        # Check for cross-team impact
        shared_patterns = ['shared/', 'common/', 'lib/', 'utils/', 'core/']
        if any(any(pattern in file_path.lower() for pattern in shared_patterns) for file_path in files):
            return "ORG"
        
        # Check for team-wide impact
        if len(files) > 5:
            return "TEAM"
        
        return "LOCAL"


# Convenience functions for common collection patterns
def collect_from_pr(pr_data: Dict[str, Any]) -> OrgSignal:
    """Convenience function to collect from PR data"""
    collector = LearningCollector()
    return collector.collect_from_pr_event(pr_data)

def collect_from_ci_failure(ci_data: Dict[str, Any]) -> OrgSignal:
    """Convenience function to collect from CI failure data"""
    collector = LearningCollector()
    return collector.collect_from_ci_event(ci_data)