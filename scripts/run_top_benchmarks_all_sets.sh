#!/usr/bin/env bash
# Прогон MA + TDTSP бенчмарков по всем наборам из top_datasets (те же имена, что в run_top_datasets.sh).
# Требуются MA_VRP_BINARY и TDTSP_PD_BINARY (или передайте пути через флаги ниже).
#
#   export MA_VRP_BINARY=.../Multi-Agent-VRP/build/app
#   export TDTSP_PD_BINARY=.../TDTSP-PD/build/tdtsp
#   ./scripts/run_top_benchmarks_all_sets.sh
#
# Один набор:
#   ./scripts/run_top_benchmarks_all_sets.sh Set_21_234

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

SETS=(
  Set_21_234
  Set_33_234
  Set_64_234
  Set_66_234
  Set_100_234
  Set_102_234
)

if [[ "${1:-}" ]]; then
  SETS=( "$@" )
fi

MA_EXTRA=( )
TD_EXTRA=( )
if [[ -n "${MA_VRP_BINARY:-}" ]]; then
  MA_EXTRA=( --binary "$MA_VRP_BINARY" )
fi
if [[ -n "${TDTSP_PD_BINARY:-}" ]]; then
  TD_EXTRA=( --binary "$TDTSP_PD_BINARY" )
fi

for s in "${SETS[@]}"; do
  echo "=== MA  top / $s ===" >&2
  python3 "${ROOT}/scripts/run_top_ma_benchmark.py" --map "$s" "${MA_EXTRA[@]}"
  echo "=== TDTSP top / $s ===" >&2
  python3 "${ROOT}/scripts/run_top_tdtsp_benchmark.py" --map "$s" "${TD_EXTRA[@]}"
done

echo "CSV MA:    ${ROOT}/experiments/ma_benchmark_top/" >&2
echo "CSV TDTSP: ${ROOT}/experiments/tdtsp_benchmark_top/" >&2
