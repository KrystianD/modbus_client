from datetime import timedelta

DefaultTimeout = timedelta(seconds=3).total_seconds()
DefaultSilentInterval = timedelta(seconds=0.05).total_seconds()

__all__ = [
    'DefaultTimeout',
    'DefaultSilentInterval',
]
