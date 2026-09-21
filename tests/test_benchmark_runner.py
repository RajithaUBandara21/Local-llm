import csv

from app.services import benchmark_runner


def fake_inference(model, prompt, temp, schema_class):
    attempt = {
        "attempt": 1, "is_valid": True, "reply": "{}", "error": "", "ttft_sec": 1.0,
        "latency_sec": 2.0, "tokens_per_sec": 3.0, "input_tokens": 4, "output_tokens": 5,
        "cpu_percent": 6.0, "ram_mb": 7.0, "vram_mb": 0,
    }
    return {"attempts_history": [attempt], "final_success": True, "total_attempts": 1, "message": ""}


def one_prompt(monkeypatch):
    monkeypatch.setattr(benchmark_runner, "run_inference_with_retry", fake_inference)
    monkeypatch.setattr(benchmark_runner, "PROMPTS", {"01": "hello"})


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def test_models_append_to_one_results_file_with_a_single_header(monkeypatch, tmp_path):
    one_prompt(monkeypatch)
    results_file = str(tmp_path / "run.csv")

    benchmark_runner.run_benchmark_for_model("model-a", results_file, [0.0], 1)
    benchmark_runner.run_benchmark_for_model("model-b", results_file, [0.0], 1)

    assert [row["model"] for row in read_rows(results_file)] == ["model-a", "model-b"]
    with open(results_file, encoding="utf-8") as file:
        assert sum(line.startswith("model,prompt_id") for line in file) == 1


def test_only_the_given_temperatures_and_runs_are_written(monkeypatch, tmp_path):
    one_prompt(monkeypatch)
    results_file = str(tmp_path / "run.csv")

    benchmark_runner.run_benchmark_for_model("model-a", results_file, [0.7, 1.2], 2)

    rows = read_rows(results_file)
    assert [(row["temperature"], row["run"]) for row in rows] == [
        ("0.7", "1"), ("0.7", "2"), ("1.2", "1"), ("1.2", "2"),
    ]


def test_results_file_name_is_shared_not_per_model(monkeypatch, tmp_path):
    monkeypatch.setattr(benchmark_runner, "RESULTS_DIR", str(tmp_path))

    name = benchmark_runner.create_results_file()

    assert name.startswith(str(tmp_path))
    assert name.split("benchmark_phase2_attempts_")[1].removesuffix(".csv").count("_") == 1
