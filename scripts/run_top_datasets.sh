#!/usr/bin/env bash
# Пакетная обработка top_datasets/* аналогично run.sh для CVRP:
#   1) канонический TOP-текст с баннером → datasets/top_normalized/<Set>/…
#   2) JSON *_tdtsp_base_*.json → datasets/many/top/<Set>/p<баланс>/
#
# Использование из корня репозитория:
#   chmod +x scripts/run_top_datasets.sh
#   ./scripts/run_top_datasets.sh
#
# Нормализация текста: последняя строка как отдельная вершина убрана из файла при:
#   TOP_DEPOT_LOOP=1 ./scripts/run_top_datasets.sh
#
# JSON по умолчанию сохраняет раздельные start/end депо (все N вершин).
# Режим одного депо (drop последней точки):
#   TOP_DEPOT_LOOP=1 ./scripts/run_top_datasets.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TOP_VARIANT="${TOP_VARIANT:-demand}"          # demand | both
TOP_SCALE="${TOP_SCALE:-1000}"                # общий scale для dist/time/limits/scores
TOP_STEM_SUFFIX="${TOP_STEM_SUFFIX:-}"        # например _full
TOP_STEM_PREFIX="${TOP_STEM_PREFIX:-}"        # например p_full_
TOP_FULL_LOAD_BOUNDS="${TOP_FULL_LOAD_BOUNDS:-0}"  # 1 -> min_load=1,max_load=points_count
TOP_DEPOT_LOOP="${TOP_DEPOT_LOOP:-0}"         # 1 -> одно депо
TOP_P_VALUES="${TOP_P_VALUES:-0.1 0.2 0.5}"   # можно переопределить, напр. "0.2"

if [[ "${TOP_VARIANT}" != "demand" && "${TOP_VARIANT}" != "both" ]]; then
  echo "Ошибка: TOP_VARIANT должен быть demand или both (сейчас: ${TOP_VARIANT})" >&2
  exit 1
fi

DEPOT_ARGS=()
if [[ "${TOP_DEPOT_LOOP}" == "1" ]]; then
  DEPOT_ARGS=( --depot-loop )
fi

JSON_EXTRA_ARGS=()
if [[ "${TOP_DEPOT_LOOP}" == "1" ]]; then
  JSON_EXTRA_ARGS=( --depot-loop )
fi
JSON_EXTRA_ARGS+=( --variant "${TOP_VARIANT}" )
JSON_EXTRA_ARGS+=( --scale "${TOP_SCALE}" )
if [[ -n "${TOP_STEM_PREFIX}" ]]; then
  JSON_EXTRA_ARGS+=( --stem-prefix "${TOP_STEM_PREFIX}" )
fi
if [[ -n "${TOP_STEM_SUFFIX}" ]]; then
  JSON_EXTRA_ARGS+=( --stem-suffix "${TOP_STEM_SUFFIX}" )
fi
if [[ "${TOP_FULL_LOAD_BOUNDS}" == "1" ]]; then
  JSON_EXTRA_ARGS+=( --full-load-bounds )
fi

# Подкаталоги top_datasets (при добавлении новых наборов — дописать сюда).
SETS=(
  Set_21_234
  Set_33_234
  Set_64_234
  Set_66_234
  Set_100_234
  Set_102_234
)

TEXT_OUT="${ROOT}/datasets/top_normalized"
JSON_MANY="${ROOT}/datasets/many/top"
JSON_ONE="${ROOT}/datasets/one/top"

if [[ "${TOP_FULL_LOAD_BOUNDS}" == "1" ]]; then
  P_VALUES=( full )
  if [[ -z "${TOP_STEM_PREFIX}" ]]; then
    JSON_EXTRA_ARGS+=( --stem-prefix "p_full_" )
  fi
else
  P_VALUES=( ${TOP_P_VALUES} )
fi

echo "=== TOP pipeline config ==="
echo "TOP_VARIANT=${TOP_VARIANT}, TOP_SCALE=${TOP_SCALE}, TOP_DEPOT_LOOP=${TOP_DEPOT_LOOP}, TOP_FULL_LOAD_BOUNDS=${TOP_FULL_LOAD_BOUNDS}, TOP_STEM_PREFIX='${TOP_STEM_PREFIX}', TOP_STEM_SUFFIX='${TOP_STEM_SUFFIX}', TOP_P_VALUES='${TOP_P_VALUES}'"

echo "=== TOP: нормализация *.txt (баннер + заголовки) ==="
for s in "${SETS[@]}"; do
  if [[ ! -d "${ROOT}/top_datasets/${s}" ]]; then
    echo "Пропуск (нет каталога): top_datasets/${s}" >&2
    continue
  fi
  # macOS bash 3.2 + set -u: пустой "${ARRAY[@]}" считается ошибкой — кратко отключаем -u
  set +u
  python3 "${ROOT}/scripts/normalize_top_txt.py" \
    -i "${ROOT}/top_datasets/${s}" \
    -o "${TEXT_OUT}" \
    "${DEPOT_ARGS[@]}"
  set -u
done

echo ""
echo "=== TOP → JSON (tdtsp_base), по тем же p, что и в run.sh ==="
for s in "${SETS[@]}"; do
  if [[ ! -d "${ROOT}/top_datasets/${s}" ]]; then
    continue
  fi
    mkdir -p "${JSON_MANY}/${s}"
    mkdir -p "${JSON_ONE}/${s}"
    for p in "${P_VALUES[@]}"; do
      p_dir="p${p}"
      if [[ "${p}" == "full" ]]; then
        p_dir="p_full"
      fi
      mkdir -p "${JSON_MANY}/${s}/${p_dir}"
      mkdir -p "${JSON_ONE}/${s}/${p_dir}"
      out_many="${JSON_MANY}/${s}"
      shopt -s nullglob
      for f in "${ROOT}/top_datasets/${s}"/*.txt; do
        set +u
        if [[ "${p}" == "full" ]]; then
          python3 "${ROOT}/scripts/top_txt_to_tdtsp_json.py" \
            -i "$f" \
            -o "${out_many}" \
            "${JSON_EXTRA_ARGS[@]}"
        else
          python3 "${ROOT}/scripts/top_txt_to_tdtsp_json.py" \
            -i "$f" \
            -o "${out_many}" \
            --balance-p "${p}" \
            "${JSON_EXTRA_ARGS[@]}"
        fi
        set -u
      done
      shopt -u nullglob
      cd "${out_many}"
      shopt -s nullglob
      tdtsp=( *tdtsp*.json )
      shopt -u nullglob
      if ((${#tdtsp[@]})); then
        mv "${tdtsp[@]}" "${JSON_ONE}/${s}/"
      fi
      shopt -s nullglob
      json=( *.json )
      shopt -u nullglob
      if ((${#json[@]})); then
        mkdir -p "${p_dir}"
        mv "${json[@]}" "${p_dir}/"
      fi
      cd "${JSON_ONE}/${s}"
      shopt -s nullglob
      json_one=( *.json )
      shopt -u nullglob
      if ((${#json_one[@]})); then
        mv "${json_one[@]}" "${p_dir}/"
      fi
      cd "${ROOT}"
    done
done

echo ""
echo "=== Готово (TOP) ==="
echo "Тексты:       ${TEXT_OUT}/<Set>/…"
echo "JSON (many):  ${JSON_MANY}/<Set>/p*/  (*_ma_* — Multi-Agent; без подстроки tdtsp)"
echo "JSON (one):   ${JSON_ONE}/<Set>/p*/  (*tdtsp*.json — как в run.sh)"
echo "В JSON по умолчанию сохраняются раздельные depots/depots_end (start/end); TOP_DEPOT_LOOP=1 включает режим одного депо."
echo "TOP_VARIANT=demand|both управляет генерацией demand/unit."
echo "TOP_SCALE задаёт общий scale для расстояния/времени/ограничений/score."
echo "TOP_STEM_PREFIX/TOP_STEM_SUFFIX управляют именами JSON-файлов."
echo "TOP_STEM_SUFFIX добавляет суффикс к имени файлов (например _full)."
echo "TOP_FULL_LOAD_BOUNDS=1 включает режим min_load=1 и max_load=points_count."
echo "Корень:       ${ROOT}"
