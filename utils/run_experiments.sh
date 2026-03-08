#!/bin/bash

FILES=(
    0.json
    10.json
    12.json
    14.json
    16.json
    18.json
    2.json
    21.json
    23.json
    25.json
    4.json 
    6.json 
    8.json
    1.json 
    11.json
    13.json
    15.json
    17.json 
    19.json 
    20.json 
    22.json 
    24.json
    3.json  
    5.json  
    7.json  
    9.json
)

# === Мета-параметры для перебора ===
# population_size (-o): размер популяции
POPULATION_SIZES=(5 10 15)

# nloop (-n): количество итераций в VNS
NLOOPS=(5 10 15)

# kMax (-k): макс. количество локальных улучшений в VND
KMAX_VALUES=(4 6 10)

# max_iter_without_solution (-i): макс. итераций без улучшения
MAX_ITER_WITHOUT_SOLUTION=(10 15 20 25)

# max_crossover_candidates (-r): макс. кандидатов для кроссовера
MAX_CROSSOVER_CANDIDATES=(3 5 7)

# === Аргументы командной строки ===
APP_PATH="${1:-./build/app}"
OUTPUT_DIR="${2:-./results}"
RUNS_PER_FILE="${3:-5}"
PATH_TO_JSONS="${4:-./jsons}"
TIME_LIMIT=50

if [ ! -f "$APP_PATH" ]; then
    echo "Ошибка: приложение не найдено по пути $APP_PATH"
    echo "Убедитесь, что приложение скомпилировано в директории build/"
    exit 1
fi

# Создаём директорию для результатов
mkdir -p "$OUTPUT_DIR"

TOTAL_FILES=${#FILES[@]}

# Подсчёт общего числа комбинаций параметров
TOTAL_COMBINATIONS=$((${#POPULATION_SIZES[@]} * ${#NLOOPS[@]} * ${#KMAX_VALUES[@]} * ${#P_VALUES[@]} * ${#MAX_ITER_WITHOUT_SOLUTION[@]} * ${#MAX_CROSSOVER_CANDIDATES[@]}))

echo "=== Параметры эксперимента ==="
echo "Файлов: $TOTAL_FILES"
echo "Комбинаций параметров: $TOTAL_COMBINATIONS"
echo "Запусков на файл: $RUNS_PER_FILE"
echo "Всего запусков: $((TOTAL_FILES * TOTAL_COMBINATIONS * RUNS_PER_FILE))"
echo "Директория результатов: $OUTPUT_DIR"
echo ""

CURRENT_COMBINATION=0

for pop_size in "${POPULATION_SIZES[@]}"; do
    for nloop in "${NLOOPS[@]}"; do
        for kmax in "${KMAX_VALUES[@]}"; do
            for max_iter in "${MAX_ITER_WITHOUT_SOLUTION[@]}"; do
                for max_cross in "${MAX_CROSSOVER_CANDIDATES[@]}"; do
                    CURRENT_COMBINATION=$((CURRENT_COMBINATION + 1))
                    
                    # Имя CSV файла с параметрами
                    CSV_FILE="${OUTPUT_DIR}/pop${pop_size}_nloop${nloop}_kmax${kmax}_maxiter${max_iter}_maxcross${max_cross}.csv"
                    
                    echo ""
                    echo "=== Комбинация $CURRENT_COMBINATION/$TOTAL_COMBINATIONS ==="
                    echo "population_size=$pop_size, nloop=$nloop, kMax=$kmax, max_iter=$max_iter, max_crossover=$max_cross"
                    echo "CSV: $CSV_FILE"
                    
                    echo "file_name,score,time,distance" > "$CSV_FILE"
                    
                    CURRENT_FILE=0
                    for file in "${FILES[@]}"; do
                        CURRENT_FILE=$((CURRENT_FILE + 1))
                        
                        if [ ! -f "$PATH_TO_JSONS/$file" ]; then
                            echo "Предупреждение: файл $file не найден, пропускаем..."
                            continue
                        fi
                        
                        echo "  [$CURRENT_FILE/$TOTAL_FILES] $file"
                        
                        for run in $(seq 1 $RUNS_PER_FILE); do
                            ./"$APP_PATH" \
                                -p "$PATH_TO_JSONS/$file" \
                                -t "$TIME_LIMIT" \
                                -c "$CSV_FILE" \
                                -o "$pop_size" \
                                -n "$nloop" \
                                -k "$kmax" \
                                -i "$max_iter" \
                                -r "$max_cross"
                            
                            if [ $? -ne 0 ]; then
                                echo "    Ошибка при запуске $run для $file"
                            fi
                        done
                    done
                done
            done
        done
    done
done

echo ""
echo "=== Готово! ==="
echo "Результаты сохранены в директории: $OUTPUT_DIR"
echo "Всего CSV файлов: $TOTAL_COMBINATIONS"
echo "Файлов данных: $TOTAL_FILES"
echo "Запусков на файл: $RUNS_PER_FILE"
