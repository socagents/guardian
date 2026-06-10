import os


class Config:
    # XLOG_API_KEY — bearer token the auth middleware enforces. Sourced
    # from the container's environment which docker-compose populates
    # from .env (CI fills .env from ${{ secrets.XLOG_API_KEY }} for
    # the deploy-compose runner; self-hosted operators set it manually).
    # Empty value = permissive mode (preserves upgrade compatibility
    # with deploys that pre-date the auth middleware).
    XLOG_API_KEY = os.getenv("XLOG_API_KEY", "")
    WORKERS_NUMBER = os.getenv("WORKERS_NUMBER", "25")
    LOGGING_DIR = os.getenv("LOGGING_DIR", "logs")
    LOGGING_STORAGE_SIZE = os.getenv("LOGGING_STORAGE_SIZE", "10M")
    LOGGING_TRUNCATE_LIMIT = os.getenv("LOGGING_TRUNCATE_LIMIT", "100")
    XSIAM_MANDATORY_PARSED_FIELDS = os.getenv(
        "XSIAM_MANDATORY_PARSED_FIELDS",
        "remote_ip,remote_port,local_ip,local_port,event_timestamp,severity,alert_name",
    )
    XSIAM_OPTIONAL_PARSED_FIELDS = os.getenv(
        "XSIAM_OPTIONAL_PARSED_FIELDS",
        "alert_description,action_status,local_ip_v6,remote_ip_v6",
    )
