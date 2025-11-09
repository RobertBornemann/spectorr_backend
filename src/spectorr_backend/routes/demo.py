# app/routes/demo.py
import json
import os
import shlex
import subprocess
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

    # Call your existing mockgen + etl, but pointed at this run dir via env
    env = os.environ.copy()
    env["SPECTORR_DATA_ROOT"] = str(rd)
    # You likely have a CLI or module entrypoint; this is a simple example:
    # 1) mockgen populates raw/
    # 2) etl reads raw/ -> writes curated/cleaned.csv
    cmds = [
        "poetry run python -m spectorr_pipeline.mockgen",  # ensure mockgen uses SPECTORR_DATA_ROOT
        "poetry run python -m spectorr_pipeline.etl",
    ]
    for cmd in cmds:
        ret = subprocess.run(shlex.split(cmd), env=env, capture_output=True, text=True)
        if ret.returncode != 0:
            raise HTTPException(500, f"step failed: {cmd}\n{ret.stderr}")

    head = (rd / "curated" / "cleaned.csv").read_text(encoding="utf-8").splitlines()[:6]
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
def stream_logs(run_id: str = Query(...)):
    rd = run_dir(run_id)
    pid_file = rd / "proc.pid"
    if not pid_file.exists():
        raise HTTPException(404, "no active process for this run")

    def event_stream():
        yield "event: info\ndata: Starting pipeline…\n\n"
        env = os.environ.copy()
        env["SPECTORR_DATA_ROOT"] = str(rd)
        cmd = "poetry run python -m spectorr_pipeline.e2e"
        with subprocess.Popen(
            shlex.split(cmd), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        ) as p:
            for line in p.stdout:
                # turn each log line into an SSE message
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
