from abc import ABC, abstractmethod


class IMetricsRepository(ABC):
    """Abstract interface for reading benchmark metrics."""

    @abstractmethod
    def get_latest_metrics(self) -> dict: pass
