"""
Background task for periodic feedback analysis.

Analyzes feedback patterns every 15 minutes and generates learning insights.
"""

import asyncio
import logging

from backend.services.feedback_learning import get_feedback_manager

logger = logging.getLogger(__name__)


class FeedbackAnalyzerTask:
    """Background task that analyzes feedback periodically."""

    def __init__(self, interval_minutes: int = 15):
        self.interval_minutes = interval_minutes
        self.running = False

    async def analyze_all_orgs(self):
        """Analyze feedback for all organizations."""
        try:
            manager = get_feedback_manager()
            analyzer = manager.analyzer

            # Get all unique org_ids from feedback records
            # Snapshot values to prevent RuntimeError if dict changes during iteration
            org_ids = set()
            feedback_records = list(manager.store.feedback_records.values())
            for feedback in feedback_records:
                if feedback.org_id:
                    org_ids.add(feedback.org_id)

            logger.info(
                "[FeedbackAnalyzer] Analyzing feedback for %d organizations",
                len(org_ids),
            )

            # Generate aggregate insights for each org
            for org_id in org_ids:
                try:
                    # Offload potentially expensive analysis to worker thread
                    insights = await asyncio.to_thread(
                        analyzer.generate_aggregate_insights, org_id
                    )
                    # Add insights to store (sync operation, but fast)
                    for insight in insights:
                        manager.store.add_insight(insight)

                    logger.info(
                        "[FeedbackAnalyzer] Generated %d insights for org: %s",
                        len(insights),
                        org_id,
                    )
                except Exception as e:
                    logger.error(
                        "[FeedbackAnalyzer] Failed to analyze org %s: %s", org_id, e
                    )

            logger.info("[FeedbackAnalyzer] ✅ Analysis complete")

        except Exception as e:
            logger.error("[FeedbackAnalyzer] Analysis failed: %s", e)

    async def run(self):
        """Run the analysis task periodically."""
        self.running = True
        logger.info(
            "[FeedbackAnalyzer] Started (interval: %d minutes)", self.interval_minutes
        )

        while self.running:
            try:
                await self.analyze_all_orgs()
            except Exception as e:
                logger.error("[FeedbackAnalyzer] Unexpected error: %s", e)

            # Wait for next interval
            await asyncio.sleep(self.interval_minutes * 60)

    def stop(self):
        """Stop the analysis task."""
        self.running = False
        logger.info("[FeedbackAnalyzer] Stopped")


# Global instance
_analyzer_task = None


def start_feedback_analyzer(interval_minutes: int = 15):
    """Start the background feedback analyzer task."""
    global _analyzer_task
    if _analyzer_task is None:
        _analyzer_task = FeedbackAnalyzerTask(interval_minutes)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.error(
                "[FeedbackAnalyzer] Cannot schedule task: no running event loop"
            )
            _analyzer_task = None  # Reset state on failure
        else:
            loop.create_task(_analyzer_task.run())
            logger.info("[FeedbackAnalyzer] Task scheduled")


def stop_feedback_analyzer():
    """Stop the background feedback analyzer task."""
    global _analyzer_task
    if _analyzer_task:
        _analyzer_task.stop()
        _analyzer_task = None


async def run_once():
    """Run a single analysis cycle (for cron jobs)."""
    logger.info("[FeedbackAnalyzer] Running one-time analysis")
    task = FeedbackAnalyzerTask()
    await task.analyze_all_orgs()
    logger.info("[FeedbackAnalyzer] One-time analysis complete")


if __name__ == "__main__":
    """CLI entrypoint for running analyzer as a standalone script."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="NAVI Feedback Analyzer Background Task"
    )
    parser.add_argument(
        "--mode",
        choices=["once", "daemon"],
        default="once",
        help="Run mode: 'once' for single run (cron), 'daemon' for continuous",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=15,
        help="Analysis interval in minutes (daemon mode only)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level",
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    try:
        if args.mode == "once":
            # Run a single analysis cycle (for cron jobs)
            asyncio.run(run_once())
            sys.exit(0)
        else:
            # Run as a daemon (continuous background task)
            task = FeedbackAnalyzerTask(interval_minutes=args.interval)
            asyncio.run(task.run())
    except KeyboardInterrupt:
        logger.info("[FeedbackAnalyzer] Received interrupt, shutting down")
        sys.exit(0)
    except Exception as e:
        logger.error("[FeedbackAnalyzer] Fatal error: %s", e)
        sys.exit(1)
