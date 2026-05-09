#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

FILES=(
    # A
    # B
    # CMT
    # F
    # M
    # P
    # Li
    # X # очень много тестовых данных
    # tai
    # Golden
    # DIMACS
    Set_33_234
    Set_64_234
    Set_66_234
    Set_100_234
    Set_102_234
)

# P_VALUES=(0.1 0.2 0.5)

for file in "${FILES[@]}"; do

    python3 scripts/run_ma_benchmark.py \
    --map ${file}  \
    --datasets-root datasets/many/top \
    --output-dir experiments/top_ma/ \
    --binary "$MA_VRP_BINARY" --variant demand

done

# for file in "${FILES[@]}"; do
#     mkdir -p "${ROOT}/datasets/many/top/${file}"
#     mkdir -p "${ROOT}/datasets/one/top/${file}"

#     for p in "${P_VALUES[@]}"; do
#         cd "$ROOT"

#         # K: VEHICLES / шаблон …-kN в имени; если не найдено — из рядом лежащего <stem>.sol (строки «Route #»).
#         # Явно предпочесть .sol при любом .vrp: добавьте --prefer-sol-agents
#         python3 scripts/build_dataset_json.py \
#             --datasets-root "top/${file}" \
#             --out-dir "datasets/many/${file}" \
#             --balance-p "${p}" \
#             --add-avg-to-scores

#         cd "${ROOT}/datasets/many/${file}"
#         mkdir -p "p${p}"
#         shopt -s nullglob
#         tdtsp=( *tdtsp*.json )
#         shopt -u nullglob
#         if ((${#tdtsp[@]})); then
#             mv "${tdtsp[@]}" "${ROOT}/datasets/one/${file}/"
#         fi

#         shopt -s nullglob
#         json=( *.json )
#         shopt -u nullglob
#         if ((${#json[@]})); then
#             mv "${json[@]}" "p${p}/"
#         fi

#         cd "${ROOT}/datasets/one/${file}"
#         mkdir -p "p${p}"
#         shopt -s nullglob
#         json_one=( *.json )
#         shopt -u nullglob
#         if ((${#json_one[@]})); then
#             mv "${json_one[@]}" "p${p}/"
#         fi
#     done
# done

echo ""
echo "=== Готово! ==="
echo "Корень проекта: ${ROOT}"
echo "Сборка: datasets/many/<набор>/p<значение>/ и datasets/one/<набор>/p<значение>/"
