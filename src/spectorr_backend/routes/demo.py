# app/routes/demo.py
import json
import os
import shlex
import subprocess
import sys
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/demo", tags=["demo"])

DATA_ROOT = Path(
    os.getenv("SPECTORR_DATA_ROOT", "~/Documents/Projects/spectorr/spectorr-data")
).expanduser()
RUNS = DATA_ROOT / "runs"
RUNS.mkdir(parents=True, exist_ok=True)


def run_dir(run_id: str) -> Path:
    return RUNS / run_id


@router.post("/start")
def start_run():
    rid = uuid.uuid4().hex[:12]
    rd = run_dir(rid)
    (rd / "raw").mkdir(parents=True, exist_ok=True)
    (rd / "curated").mkdir(parents=True, exist_ok=True)
    return {"run_id": rid}


@router.post("/mockgen")
def generate_mock(run_id: str = Query(...), n: int = Query(200, ge=10, le=2000)):
    rd = run_dir(run_id)
    if not rd.exists():
        raise HTTPException(404, "run_id not found; call /demo/start first")

    env = os.environ.copy()
    env["SPECTORR_DATA_ROOT"] = str(rd)

    steps = [
        [sys.executable, "-m", "spectorr_pipeline.mockgen", "--n", str(n)],
        [sys.executable, "-m", "spectorr_pipeline.etl"],
    ]

    for cmd in steps:
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if proc.returncode != 0:
            # Log to server console
            print("=== DEMO /mockgen step failed ===", file=sys.stderr, flush=True)
            print("CMD:", " ".join(cmd), file=sys.stderr, flush=True)
            print("STDOUT (tail):", proc.stdout[-800:], file=sys.stderr, flush=True)
            print("STDERR (tail):", proc.stderr[-1200:], file=sys.stderr, flush=True)
            # Return detail to the UI
            raise HTTPException(
                status_code=500,
                detail={
                    "step": " ".join(cmd),
                    "stdout_tail": proc.stdout[-800:],
                    "stderr_tail": proc.stderr[-1200:],
                },
            )

    cleaned = rd / "curated" / "cleaned.csv"
    if not cleaned.exists():
        raise HTTPException(500, "cleaned.csv missing after ETL")
    head = cleaned.read_text(encoding="utf-8").splitlines()[:20]
    return {"run_id": run_id, "cleaned_head": head}


@router.get("/raw")
def get_raw(run_id: str = Query(...)):
    rd = run_dir(run_id)
    cleaned = rd / "curated" / "cleaned.csv"
    if not cleaned.exists():
        raise HTTPException(404, "cleaned.csv missing; run /demo/mockgen")
    # Return a small preview to keep payload tiny
    lines = cleaned.read_text(encoding="utf-8").splitlines()
    return {"run_id": run_id, "rows": lines[:50], "total_rows": len(lines) - 1}


@router.post("/run")
def run_pipeline(run_id: str = Query(...), asset_id: str | None = None, date: str | None = None):
    rd = run_dir(run_id)
    if not (rd / "curated" / "cleaned.csv").exists():
        raise HTTPException(400, "No cleaned.csv. Run /demo/mockgen first.")

    env = os.environ.copy()
    env["SPECTORR_DATA_ROOT"] = str(rd)

    # Launch the pipeline as a subprocess that prints logs we can stream separately
    # Alternatively, you can run synchronously and return when done.
    cmd = "poetry run python -m spectorr_pipeline.e2e"
    if asset_id:
        cmd += f" {shlex.quote(asset_id)}"
    if date:
        cmd += f" {shlex.quote(date)}"

    proc = subprocess.Popen(
        shlex.split(cmd), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )

    # Store PID to a file so the stream endpoint can attach (simple approach)
    (rd / "proc.pid").write_text(str(proc.pid), encoding="utf-8")
    return {"run_id": run_id, "status": "started"}


@router.get("/stream")
def stream_pipeline(run_id: str = Query(...), asset_id: str | None = None, date: str | None = None):
    rd = run_dir(run_id)
    if not (rd / "curated" / "cleaned.csv").exists():
        raise HTTPException(400, "No cleaned.csv. Run /demo/mockgen first.")

    def event_stream():
        # tell client we started
        yield "event: info\ndata: starting pipeline…\n\n"

        env = os.environ.copy()
        env["SPECTORR_DATA_ROOT"] = str(rd)
        env["PYTHONUNBUFFERED"] = "1"  # 👈 critical: unbuffered Python
        cmd = [sys.executable, "-m", "spectorr_pipeline.e2e"]
        if asset_id:
            cmd.append(asset_id)
        if date:
            cmd.append(date)

        # bufsize=1 + text=True makes it line-buffered on our side
        with subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        ) as p:
            assert p.stdout is not None
            for line in p.stdout:
                # forward each log line (your adapter prints with flush=True)
                yield f"data: {line.rstrip()}\n\n"
            code = p.wait()
            status = "done" if code == 0 else f"error({code})"
            yield f"event: status\ndata: {status}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/insights")
def get_insights(run_id: str = Query(...)):
    rd = run_dir(run_id)
    insights = rd / "curated" / "insights.json"
    if not insights.exists():
        raise HTTPException(404, "insights.json missing; run /demo/run")
    data = json.loads(insights.read_text(encoding="utf-8"))
    return {"run_id": run_id, "count": len(data), "items": data}
