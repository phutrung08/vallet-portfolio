"""Every size and count cap in one place."""

MAX_REQUEST_BODY_BYTES = 64 * 1024

MAX_ACTIVE_MEMBERS = 50
MAX_TOTAL_MEMBERS = 200
MAX_TRIPS_PER_DEVICE = 50
# Live means not soft-deleted: deleting frees room again.
MAX_LIVE_EXPENSES = 2_000
MAX_LIVE_CONTRIBUTIONS = 1_000
MAX_LIVE_PAYMENTS = 1_000

# Requests per client IP per window (token buckets, see api/rate_limit.py).
RATE_WINDOW_SECONDS = 60
RATE_LIMIT_ALL = 300
RATE_LIMIT_JOIN = 20  # POST /join and /join/preview: share tokens must not be guessable
RATE_LIMIT_TRIP_CREATE = 10  # POST /trips: prevent unauthenticated trip flooding
RATE_LIMIT_WRITES = 120  # every other POST, PUT, PATCH and DELETE
# Buckets kept in memory; the least recently used is dropped beyond this.
RATE_LIMIT_TRACKED_KEYS = 10_000
