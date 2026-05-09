#!/usr/bin/env bash
# Пакетная отрисовка TOP .txt (как utils/draw.py, но для формата TOP).
# Без окон — только PNG в выходной каталог.
#
#   ./scripts/plot_top_dataset.sh top_datasets/Set_21_234
#   ./scripts/plot_top_dataset.sh datasets/top_normalized/Set_21_234 figures/top_Set21
#
# В средах без записи в ~/.matplotlib задайте каталог кэша, например:
#   export MPLCONFIGDIR=/tmp/mplconfig

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IN="${1:?Укажите каталог с *.txt (TOP)}"
OUT="${2:-${ROOT}/figures/top_preview}"

export MPLCONFIGDIR="${MPLCONFIGDIR:-${TMPDIR:-/tmp}/mplconfig_draw_top}"
mkdir -p "$OUT" "$MPLCONFIGDIR"

shopt -s nullglob
files=( "${IN}"/*.txt )
shopt -u nullglob
if ((${#files[@]} == 0)); then
  echo "Нет *.txt в ${IN}" >&2
  exit 1
fi

for f in "${files[@]}"; do
  stem=$(basename "$f" .txt)
  python3 "${ROOT}/utils/draw_top.py" "$f" --no-show -o "${OUT}/${stem}.png"
done

echo "Сохранено ${#files[@]} файлов в ${OUT}"
