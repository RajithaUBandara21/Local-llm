import csv
import glob
import os

from app.repositories.base import IMetricsRepository


class CSVMetricsRepository(IMetricsRepository):
    """Handles reading and parsing CSV files from the local filesystem."""

    def __init__(self, results_dir: str):
        self.results_dir = results_dir

    def get_latest_metrics(self) -> dict:
        if not os.path.exists(self.results_dir):
            raise FileNotFoundError("Results directory not found.")

        csv_files = glob.glob(os.path.join(self.results_dir, "*.csv"))
        if not csv_files:
            raise FileNotFoundError("No benchmark CSV files found.")

        latest_file = max(csv_files, key=os.path.getctime)
        metrics = []
        with open(latest_file, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                metrics.append(row)

        return {
            "latest_benchmark_file": os.path.basename(latest_file),
            "total_runs": len(metrics),
            "data": metrics
        }
