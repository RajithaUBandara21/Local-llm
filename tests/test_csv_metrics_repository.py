import csv
import os

import pytest

from main import CSVMetricsRepository

HEADER = ["model", "prompt_id", "latency_sec"]


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(HEADER)
        writer.writerows(rows)


def test_missing_directory_raises(tmp_path):
    repo = CSVMetricsRepository(str(tmp_path / "does-not-exist"))

    with pytest.raises(FileNotFoundError, match="Results directory not found."):
        repo.get_latest_metrics()


def test_directory_without_csv_files_raises(tmp_path):
    (tmp_path / "notes.txt").write_text("not a benchmark")

    with pytest.raises(FileNotFoundError, match="No benchmark CSV files found."):
        CSVMetricsRepository(str(tmp_path)).get_latest_metrics()


def test_single_csv_returns_rows_as_string_dicts(tmp_path):
    write_csv(tmp_path / "run.csv", [["llama3.2", "01", "1.5"], ["llama3.2", "02", "2.25"]])

    result = CSVMetricsRepository(str(tmp_path)).get_latest_metrics()

    assert result == {
        "latest_benchmark_file": "run.csv",
        "total_runs": 2,
        "data": [
            {"model": "llama3.2", "prompt_id": "01", "latency_sec": "1.5"},
            {"model": "llama3.2", "prompt_id": "02", "latency_sec": "2.25"},
        ],
    }


def test_header_only_csv_has_no_runs(tmp_path):
    write_csv(tmp_path / "empty.csv", [])

    result = CSVMetricsRepository(str(tmp_path)).get_latest_metrics()

    assert result["latest_benchmark_file"] == "empty.csv"
    assert result["total_runs"] == 0
    assert result["data"] == []


def test_latest_csv_is_the_one_with_greatest_ctime(tmp_path, monkeypatch):
    write_csv(tmp_path / "old.csv", [["mistral", "01", "9.0"]])
    write_csv(tmp_path / "new.csv", [["llama3.2", "01", "1.0"]])
    # A newer non-CSV file must not be picked, and real ctime semantics differ by OS.
    (tmp_path / "newest.txt").write_text("ignored")
    ctimes = {"old.csv": 100.0, "new.csv": 200.0, "newest.txt": 300.0}
    monkeypatch.setattr(os.path, "getctime", lambda path: ctimes[os.path.basename(path)])

    result = CSVMetricsRepository(str(tmp_path)).get_latest_metrics()

    assert result["latest_benchmark_file"] == "new.csv"
    assert result["data"] == [{"model": "llama3.2", "prompt_id": "01", "latency_sec": "1.0"}]
