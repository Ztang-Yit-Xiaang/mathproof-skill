"""Experiment runner (S3.1.T1) and R adapter (S3.1.T4)."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from .ledger import Ledger


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _python_env_lock() -> tuple[str, str]:
    dists = sorted(
        f"{d.metadata['Name']}=={d.version}"
        for d in importlib.metadata.distributions()
        if d.metadata.get("Name")
    )
    text = sys.version + "\n" + "\n".join(dists)
    return _sha256_hex(text.encode("utf-8")), "python-metadata"


def _r_env_lock(code_path: Path, rscript: str | None) -> tuple[str, str | None]:
    renv_path = code_path.parent / "renv.lock"
    if renv_path.is_file():
        return _sha256_hex(renv_path.read_bytes()), "renv.lock"
    if rscript is None:
        return _sha256_hex(b""), None
    expr = (
        "cat(R.version.string, '\\n', sep='');"
        "ip <- installed.packages()[, c('Package', 'Version'), drop=FALSE];"
        "lines <- sort(paste0(ip[, 'Package'], '==', ip[, 'Version']));"
        "cat(paste(lines, collapse='\\n'))"
    )
    try:
        proc = subprocess.run(
            [rscript, "--vanilla", "-e", expr],
            capture_output=True,
            text=True,
            timeout=30,
        )
        text = proc.stdout if proc.returncode == 0 else ""
    except Exception:
        text = ""
    return _sha256_hex(text.encode("utf-8")), "r-installed"


def _check_memory_limit(memory_mb: int) -> bool:
    limit_bytes = int(memory_mb) * 1024 * 1024
    pid = os.fork()
    if pid == 0:
        try:
            resource.setrlimit(resource.RLIMIT_AS, (limit_bytes, limit_bytes))
            os._exit(0)
        except Exception:
            os._exit(1)
    else:
        _, status = os.waitpid(pid, 0)
        return os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0


def run_experiment(
    code_path: str | os.PathLike[str],
    *,
    language: str,
    seed: int,
    params: dict[str, Any],
    timeout_s: int | float = 60,
    memory_mb: int = 2048,
) -> dict[str, Any]:
    """Run a single-file Python or R experiment in an isolated temp directory."""
    if language not in ("python", "r"):
        raise ValueError(f"unsupported language: {language}")

    src_path = Path(code_path).resolve()
    code_bytes = src_path.read_bytes()
    code_hash = _sha256_hex(code_bytes)

    if language == "python":
        interpreter: str | None = sys.executable
        env_lock_hash, env_lock_source = _python_env_lock()
    else:
        interpreter = shutil.which("Rscript")
        env_lock_hash, env_lock_source = _r_env_lock(src_path, interpreter)

    if interpreter is None:
        return {
            "language": language,
            "code_hash": code_hash,
            "env_lock_hash": _sha256_hex(b""),
            "seed": seed,
            "params": params,
            "limits": {"timeout_s": timeout_s, "memory_mb": memory_mb},
            "outcome": "error",
            "results": None,
            "results_hash": None,
            "violations": [],
            "diagnostics": {
                "returncode": None,
                "stderr_tail": "",
                "interpreter": None,
                "unavailable": True,
                "memory_limit_enforced": False,
                "env_lock_source": env_lock_source,
                "sandboxed": False,
                "seconds": 0.0,
            },
            "tags": [],
        }

    can_enforce_mem = _check_memory_limit(memory_mb)
    limit_bytes = int(memory_mb) * 1024 * 1024

    def _preexec() -> None:
        os.setsid()
        if can_enforce_mem:
            try:
                resource.setrlimit(resource.RLIMIT_AS, (limit_bytes, limit_bytes))
            except Exception:
                pass

    with tempfile.TemporaryDirectory(prefix="mps_exp_") as tmp_dir:
        tmp_path = Path(tmp_dir).resolve()
        prog_name = src_path.name or ("experiment.py" if language == "python" else "experiment.R")
        prog_file = tmp_path / prog_name
        prog_file.write_bytes(code_bytes)
        out_file = tmp_path / "mp_out.json"

        cmd = (
            [interpreter, "-I", str(prog_file)]
            if language == "python"
            else [interpreter, "--vanilla", str(prog_file)]
        )

        child_env: dict[str, str] = {}
        for key in ("PATH", "HOME", "LANG"):
            if key in os.environ:
                child_env[key] = os.environ[key]
        child_env["MP_SEED"] = str(int(seed))
        child_env["MP_PARAMS"] = _canonical_json(params)
        child_env["MP_OUT"] = str(out_file)

        t0 = time.monotonic()
        timed_out = False
        returncode: int | None = None
        stderr_text = ""

        proc = subprocess.Popen(
            cmd,
            cwd=str(tmp_path),
            env=child_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=_preexec,
        )
        try:
            _, stderr_text = proc.communicate(timeout=timeout_s)
            returncode = proc.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                _, stderr_text = proc.communicate(timeout=5)
            except Exception:
                stderr_text = ""
            returncode = proc.returncode

        elapsed = round(time.monotonic() - t0, 6)

        results: dict[str, Any] | None = None
        results_hash: str | None = None
        violations: list[ dict[str, Any] ] = []

        if timed_out:
            outcome = "timeout"
        elif returncode == 0 and out_file.is_file():
            try:
                parsed = json.loads(out_file.read_text(encoding="utf-8"))
                if isinstance(parsed, dict):
                    outcome = "completed"
                    results = parsed
                    results_hash = _sha256_hex(_canonical_json(results).encode("utf-8"))
                    raw_violations = results.get("violations")
                    if isinstance(raw_violations, list):
                        violations = [v for v in raw_violations if isinstance(v, dict)]
                else:
                    outcome = "error"
            except Exception:
                outcome = "error"
        else:
            outcome = "error"

    return {
        "language": language,
        "code_hash": code_hash,
        "env_lock_hash": env_lock_hash,
        "seed": seed,
        "params": params,
        "limits": {"timeout_s": timeout_s, "memory_mb": memory_mb},
        "outcome": outcome,
        "results": results,
        "results_hash": results_hash,
        "violations": violations if outcome == "completed" else [],
        "diagnostics": {
            "returncode": returncode,
            "stderr_tail": (stderr_text or "")[-2000:],
            "interpreter": interpreter,
            "unavailable": False,
            "memory_limit_enforced": can_enforce_mem,
            "env_lock_source": env_lock_source,
            "sandboxed": False,
            "seconds": elapsed,
        },
        "tags": [],
    }


def record_experiment(
    ledger: Ledger,
    claim: str,
    code_path: str | os.PathLike[str],
    record: dict[str, Any],
    actor: dict[str, str],
) -> dict[str, Any]:
    """Store code and results artifacts and append an experiment event."""
    code_bytes = Path(code_path).read_bytes()
    digest = ledger.put_artifact(code_bytes)
    if digest != record.get("code_hash"):
        raise ValueError(f"code artifact digest {digest} does not match record code_hash {record.get('code_hash')}")

    results = record.get("results")
    if results is not None:
        results_bytes = _canonical_json(results).encode("utf-8")
        res_digest = ledger.put_artifact(results_bytes)
        if record.get("results_hash") and res_digest != record["results_hash"]:
            raise ValueError("results_hash does not match canonical JSON digest")

    # Keep the renv lock, so a re-run in a fresh directory sees the same lock (its digest is env_lock_hash).
    if (record.get("diagnostics") or {}).get("env_lock_source") == "renv.lock":
        lock_digest = ledger.put_artifact((Path(code_path).parent / "renv.lock").read_bytes())
        if lock_digest != record.get("env_lock_hash"):
            raise ValueError("renv.lock changed between the run and recording")

    data = {k: v for k, v in record.items() if k != "results"}
    return ledger.append("experiment", claim, data, actor)


def rerun_experiment(
    ledger: Ledger,
    event: dict[str, Any],
    timeout_s: int | float | None = None,
    memory_mb: int | None = None,
) -> list[str]:
    """Re-run a recorded experiment event from its stored code artifact and compare."""
    data = event["data"]
    code_bytes = ledger.get_artifact(data["code_hash"])
    language = data["language"]
    suffix = ".py" if language == "python" else ".R"
    limits = data.get("limits") or {}
    use_timeout = timeout_s if timeout_s is not None else limits.get("timeout_s", 60)
    use_memory = memory_mb if memory_mb is not None else limits.get("memory_mb", 2048)

    with tempfile.TemporaryDirectory(prefix="mps_rerun_") as tmp_dir:
        code_file = Path(tmp_dir) / f"program{suffix}"
        code_file.write_bytes(code_bytes)
        if (data.get("diagnostics") or {}).get("env_lock_source") == "renv.lock":
            (Path(tmp_dir) / "renv.lock").write_bytes(ledger.get_artifact(data["env_lock_hash"]))
        fresh = run_experiment(
            code_file,
            language=language,
            seed=data["seed"],
            params=data["params"],
            timeout_s=use_timeout,
            memory_mb=use_memory,
        )

    differences: list[str] = []
    if fresh["outcome"] != data.get("outcome"):
        differences.append(f"outcome differs: recorded {data.get('outcome')}, rerun {fresh['outcome']}")
    if fresh["results_hash"] != data.get("results_hash"):
        differences.append(f"results_hash differs: recorded {data.get('results_hash')}, rerun {fresh['results_hash']}")
    if fresh["env_lock_hash"] != data.get("env_lock_hash"):
        differences.append(
            f"environment changed: recorded {data.get('env_lock_hash')}, rerun {fresh['env_lock_hash']}"
        )
    return differences
