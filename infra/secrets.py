# infra/secrets.py
"""
Secrets management (can be extended with GCP Secret Manager or AWS Secrets Manager).
For MVP, reads from environment variables.
"""
import os


def get_secret(key: str, default: str = None) -> str:
    """
    Retrieve a secret from environment variables.
    """
    return os.environ.get(key, default)
