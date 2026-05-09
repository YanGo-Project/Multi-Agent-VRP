#!/usr/bin/env python3
"""
Прогон Multi-Agent-VRP по JSON из TOP-пайплайна (run_top_datasets.sh).

По сути вызывает scripts/run_ma_benchmark.py с путями по умолчанию:
  --datasets-root  <repo>/datasets/many/top
  --output-dir     <repo>/experiments/ma_benchmark_top

Остальные аргументы (--map, --binary, --variant, …) те же, что у run_ma_benchmark.py.

Пример:
  export MA_VRP_BINARY=/path/to/Multi-Agent-VRP/build/app
  python3 scripts/run_top_ma_benchmark.py --map Set_21_234

См. также: run_top_tdtsp_benchmark.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main() -> int:
    root = _repo_root()
    child = root / "scripts" / "run_ma_benchmark.py"
    args = sys.argv[1:]
    ds = root / "datasets" / "many" / "top"
    out = root / "experiments" / "ma_benchmark_top"

    prefix: list[str] = []
    if "--datasets-root" not in args:
        prefix.extend(["--datasets-root", str(ds)])
    if "--output-dir" not in args:
        prefix.extend(["--output-dir", str(out)])

    cmd = [sys.executable, str(child)] + prefix + args
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
