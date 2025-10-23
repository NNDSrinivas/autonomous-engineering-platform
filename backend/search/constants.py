"""Search and indexing constants shared across modules"""

# Reindexing limits and thresholds
MAX_CHANNELS_PER_SYNC = 20  # Slack channels to sync per request
SLACK_HISTORY_LIMIT = 300  # Messages per channel per sync
CONFLUENCE_PAGE_LIMIT = 200  # Pages to fetch per sync
MAX_CONTENT_LENGTH = 200000  # Max characters for text content
MAX_MEETINGS_PER_SYNC = 1000  # Meeting records to sync per request
