#!/usr/bin/env python3
"""
Прогон TDTSP-PD по JSON из TOP-пайплайна (run_top_datasets.sh → datasets/one/top).

Вызывает scripts/run_tdtsp_benchmark.py с путями по умолчанию:
  --datasets-root  <repo>/datasets/one/top
  --output-dir     <repo>/experiments/tdtsp_benchmark_top

Пример:
  export TDTSP_PD_BINARY=/path/to/TDTSP-PD/build/tdtsp
  python3 scripts/run_top_tdtsp_benchmark.py --map Set_21_234

См. также: run_top_ma_benchmark.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main() -> int:
    root = _repo_root()
    child = root / "scripts" / "run_tdtsp_benchmark.py"
    args = sys.argv[1:]
    ds = root / "datasets" / "one" / "top"
    out = root / "experiments" / "tdtsp_benchmark_top"

    prefix: list[str] = []
    if "--datasets-root" not in args:
        prefix.extend(["--datasets-root", str(ds)])
    if "--output-dir" not in args:
        prefix.extend(["--output-dir", str(out)])

    cmd = [sys.executable, str(child)] + prefix + args
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
