"""Search and indexing constants shared across modules"""

# Reindexing limits and thresholds
MAX_CHANNELS_PER_SYNC = 20  # Slack channels to sync per request
SLACK_HISTORY_LIMIT = 300  # Messages per channel per sync
CONFLUENCE_PAGE_LIMIT = 200  # Pages to fetch per sync
MAX_CONTENT_LENGTH = 200000  # Max characters for text content
MAX_MEETINGS_PER_SYNC = 1000  # Meeting records to sync per request
# Multiplier to allow some HTML tag overhead when truncating raw HTML before parsing
# We parse at up to HTML_OVERHEAD_MULTIPLIER * MAX_CONTENT_LENGTH characters to
# allow for HTML tags and attributes that expand the raw size relative to text.
HTML_OVERHEAD_MULTIPLIER = 2
