import os
import subprocess

import psutil


def _ollama_pids():
    """Return Ollama's PID tree, including the server's child processes."""
    roots = []
    for process in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            name = (process.info["name"] or "").lower()
            command = " ".join(process.info["cmdline"] or []).lower()
            if "ollama" in name or "ollama" in command:
                roots.append(process)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    processes = {}
    for root in roots:
        try:
            processes[root.pid] = root
            processes.update({child.pid: child for child in root.children(recursive=True)})
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return processes


def _gpu_memory_for_pids(pids):
    """Return VRAM used by the supplied PIDs, or None without NVIDIA tools."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-compute-apps=pid,used_memory",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None

    if result.returncode != 0:
        return None

    used_mb = 0
    for line in result.stdout.splitlines():
        try:
            pid_text, memory_text = line.split(",", 1)
            if int(pid_text.strip()) in pids:
                used_mb += int(memory_text.strip())
        except ValueError:
            continue
    return used_mb


def capture_process_usage():
    """Capture CPU time, resident RAM, and Ollama-attributed VRAM."""
    app = psutil.Process(os.getpid())
    ollama = _ollama_pids()
    processes = {app.pid: app, **ollama}
    cpu_time = 0.0
    ram_mb = 0.0

    for process in processes.values():
        try:
            times = process.cpu_times()
            cpu_time += times.user + times.system
            ram_mb += process.memory_info().rss / (1024 * 1024)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    ollama_pids = set(ollama)
    return {
        "cpu_time": cpu_time,
        "ram_mb": ram_mb,
        "ollama_pids": ollama_pids,
        "vram_mb": _gpu_memory_for_pids(ollama_pids),
    }
