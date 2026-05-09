import os
import re
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# ============================================================
# НАСТРОЙКИ (измените при необходимости)
# ============================================================
PATH_MA = "experiments/ma_benchmark_original_demand"          # папка с MA
PATH_BASELINE = "experiments/tdtsp_benchmark_original_demand" # папка с Baseline
DATASETS = ["A", "B", "CMT", "DIMACS", "F", "Golden", "Li", "M", "P", "tai"]
P_STRINGS = ["p10", "p20", "p50"]
P_VALUES = [0.1, 0.2, 0.5]                  # подписи p
# P_VALUES = [0.1]                  # подписи p
OUTPUT_DIR = "comparison_plots"
os.makedirs(OUTPUT_DIR, exist_ok=True)

CLIP_LIMIT = 100  # максимальное отображаемое относительное изменение ±100%

TASK_PATTERN = re.compile(r'([A-Za-z]+-n\d+-k\d+)')

ANALYZED_CDV="comparison_plots_avg/data.csv"

def extract_task_name(json_path: str) -> str:
    match = TASK_PATTERN.search(json_path)
    if match:
        return match.group(1)
    base = os.path.basename(json_path).replace('.json', '')
    base = re.sub(r'_p\d+\.\d+.*', '', base)
    return base

def load_data(directory, dataset, p_str):
    filename = f"{dataset}_{p_str}.csv"
    filepath = os.path.join(directory, filename)
    if not os.path.exists(filepath):
        print(f"    ❌ {filepath} не найден")
        return None
    df = pd.read_csv(filepath)
    df['task'] = df['json_path'].apply(extract_task_name)
    idx = P_STRINGS.index(p_str)
    df['p'] = P_VALUES[idx]
    return df[['task', 'sum_score', 'feasible_agents_num', 'sum_distance', 'points_count', 'agents_count', 'p']]

def relative_change(ma, baseline):
    ma = np.array(ma, dtype=float)
    baseline = np.array(baseline, dtype=float)
    with np.errstate(divide='ignore', invalid='ignore'):
        rel = np.where(np.abs(baseline) > 1e-9, (ma - baseline) / np.abs(baseline), np.nan)
    return rel

def plot_with_clipping(ax, x, y, label, marker='o', linestyle='-', clip_limit=CLIP_LIMIT, color=None):
    """Рисует линию, обрезая y для отображения, но без подписей выбросов (упрощённо)."""
    y_clipped = np.clip(y, -clip_limit, clip_limit)
    ax.plot(x, y_clipped, marker=marker, linestyle=linestyle, label=label, color=color)

def color_xticklabels(ax, condition_colors):
    """
    Окрашивает метки оси X в соответствии со списком цветов.
    condition_colors: список цветов для каждого xtick.
    """
    for xtick, col in zip(ax.get_xticklabels(), condition_colors):
        xtick.set_color(col)

def get_task_color(both_ok, ma_not_ok, bs_not_ok):
    if both_ok:
        return 'black'
    elif ma_not_ok and not bs_not_ok:
        return 'red'
    elif bs_not_ok and not ma_not_ok:
        return 'green'
    else:  # оба не ок
        return 'orange'

def main():
    print("=" * 70)
    print("Построение графиков с цветовой маркировкой по выполнению ограничений")
    print("=" * 70)

    if not os.path.exists(PATH_MA):
        print(f"ОШИБКА: папка MA не найдена: {PATH_MA}")
        return
    if not os.path.exists(PATH_BASELINE):
        print(f"ОШИБКА: папка Baseline не найдена: {PATH_BASELINE}")
        return

    # Загрузка всех данных
    ma_data = {ds: {} for ds in DATASETS}
    bs_data = {ds: {} for ds in DATASETS}
    for ds in DATASETS:
        for p_str in P_STRINGS:
            print(f"\n[{ds}] Загрузка {p_str}...")
            df_ma = load_data(PATH_MA, ds, p_str)
            if df_ma is not None:
                ma_data[ds][p_str] = df_ma
            df_bs = load_data(PATH_BASELINE, ds, p_str)
            if df_bs is not None:
                bs_data[ds][p_str] = df_bs

    # Обработка каждого датасета
    for ds in DATASETS:
        print(f"\n--- Обработка {ds} ---")
        combined_list = []
        for p_str in P_STRINGS:
            df_ma = ma_data[ds].get(p_str)
            df_bs = bs_data[ds].get(p_str)
            if df_ma is None or df_bs is None:
                print(f"  ⚠️ Для p={p_str} нет данных в одной из папок, пропускаем")
                continue

            merged = pd.merge(
                df_ma[['task', 'sum_score', 'feasible_agents_num', 'sum_distance', 'points_count', 'agents_count', 'p']],
                df_bs[['task', 'sum_score', 'feasible_agents_num', 'sum_distance']],
                on='task',
                suffixes=('_ma', '_baseline')
            )
            merged = merged.sort_values('points_count')
            # Относительные изменения (в процентах)
            merged['rel_score'] = relative_change(merged['sum_score_ma'], merged['sum_score_baseline']) * 100
            merged['rel_distance'] = relative_change(merged['sum_distance_ma'], merged['sum_distance_baseline']) * 100
            # Флаги допустимости
            merged['ma_ok'] = merged['feasible_agents_num_ma'] == merged['agents_count']
            merged['bs_ok'] = merged['feasible_agents_num_baseline'] == merged['agents_count']
            merged['both_ok'] = merged['ma_ok'] & merged['bs_ok']
            # Цвет для подписи оси X
            merged['task_color'] = merged.apply(
                lambda row: get_task_color(row['both_ok'], not row['ma_ok'], not row['bs_ok']), axis=1
            )
            combined_list.append(merged)

        if not combined_list:
            print(f"  ❌ Нет общих задач для {ds}, пропускаем")
            continue

        all_data = pd.concat(combined_list, ignore_index=True)

        # ------------------- 1. Общая картинка: два линейных графика (score, distance) в ряд -------------------
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        metrics = [('score', 'rel_score', 'sum_score'), ('distance', 'rel_distance', 'sum_distance')]
        titles = ['Относительное изменение sum_score (%)',
                  'Относительное изменение sum_distance (%)']

        for i, (name, col, metric_name) in enumerate(metrics):
            ax = axes[i]
            for p_val in P_VALUES:
                sub = all_data[all_data['p'] == p_val].copy()
                if sub.empty:
                    continue
                # Заменяем rel на nan для тех строк, где оба метода недопустимы
                sub.loc[~sub['both_ok'], col] = np.nan
                tasks = sub['task'].values
                y_vals = sub[col].values
                plot_with_clipping(ax, tasks, y_vals, label=f'p={p_val}', marker='o', linestyle='-')
            ax.axhline(y=0, color='k', linestyle='--', linewidth=0.8)
            ax.set_xlabel('Инстанс')
            ax.set_ylabel('Относительное изменение, %')
            ax.set_title(titles[i])
            ax.tick_params(axis='x', rotation=45, labelsize=8)
            ax.set_ylim(-CLIP_LIMIT - 10, CLIP_LIMIT + 10)
            ax.legend()
            ax.grid(True, alpha=0.3)

            # Средние значения только по both_ok
            text_lines = []
            for p_val in P_VALUES:
                sub_p = all_data[all_data['p'] == p_val]
                if not sub_p.empty:
                    both_ok_mask = sub_p['both_ok']
                    if both_ok_mask.any():
                        mean_val = sub_p.loc[both_ok_mask, col].mean()
                        cnt = both_ok_mask.sum()
                        text_lines.append(f'p={p_val}: {mean_val:.1f}% (Карт: {cnt})')
                        print(f'p={p_val}: {mean_val:.1f}% (Карт: {cnt})')
                    else:
                        text_lines.append(f'p={p_val}: нет карт с выполнением у обоих')
            ax.annotate('\n'.join(text_lines), xy=(0.98, 0.02), xycoords='axes fraction',
                        ha='right', va='bottom', fontsize=8,
                        bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))

            # Добавляем легенду цветов подписей (один раз для обоих графиков)
            if i == 0:
                color_legend = (
                    "Цвет подписи задачи:\n"
                    "чёрный – оба метода допустимы\n"
                    "красный – только MA недопустим\n"
                    "зелёный – только Baseline недопустим\n"
                    "оранжевый – оба недопустимы"
                )
                ax.annotate(color_legend, xy=(1.02, 0.5), xycoords='axes fraction',
                            ha='left', va='center', fontsize=8,
                            bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))

        plt.suptitle(f'Датасет {ds}: относительное изменение метрик (MA vs Baseline)\n'
                     f'Точки рисуются только если оба метода допустимы', fontsize=14)
        plt.tight_layout()
        plt.savefig(os.path.join(OUTPUT_DIR, f'{ds}_relative_changes.png'), dpi=150)
        plt.close()

        # ------------------- 2. Каждый линейный график отдельно (с цветными подписями осей) -------------------
        for i, (name, col, metric_name) in enumerate(metrics):
            plt.figure(figsize=(10, 5))
            ax = plt.gca()
            # Для каждого p строим с фильтром both_ok
            for p_val in P_VALUES:
                sub = all_data[all_data['p'] == p_val].copy()
                if sub.empty:
                    continue
                sub.loc[~sub['both_ok'], col] = np.nan
                tasks = sub['task'].values
                y_vals = sub[col].values
                plot_with_clipping(ax, tasks, y_vals, label=f'p={p_val}', marker='o', linestyle='-')
            plt.axhline(y=0, color='k', linestyle='--', linewidth=0.8)
            plt.xlabel('Инстанс')
            plt.ylabel('Относительное изменение, %')
            plt.title(f'{ds}: {titles[i]}')
            plt.ylim(-CLIP_LIMIT - 10, CLIP_LIMIT + 10)
            plt.xticks(rotation=45, ha='right')
            plt.legend()
            plt.grid(True, alpha=0.3)

            # Устанавливаем цвет подписей осей в зависимости от статуса (для всех p вместе)
            # Берём уникальные задачи из first_p (порядок сохраняется)
            first_p = P_VALUES[0]
            sub_first = all_data[all_data['p'] == first_p]
            if not sub_first.empty:
                tasks_order = sub_first['task'].values
                # Для каждой задачи определяем цвет (если хотя бы для одного p цвет отличается – приоритет? 
                # Поскольку цвет задачи может меняться в зависимости от p, для единой оси X обычно берут агрегированный цвет, 
                # но мы предлагаем для простоты взять цвет, соответствующий первому p (или агрегировать).
                # Для наглядности сделаем агрегацию: если для задачи есть хоть один p, где оба недопустимы -> оранжевый,
                # иначе если есть p, где только MA недопустим -> красный,
                # иначе если есть p, где только baseline недопустим -> зелёный,
                # иначе чёрный.
                task_colors = []
                for t in tasks_order:
                    task_data = all_data[all_data['task'] == t]
                    if (task_data['both_ok'] == False).all() and (task_data['ma_ok'] == False).all() and (task_data['bs_ok'] == False).all():
                        task_colors.append('orange')  # все p – оба недопустимы
                    elif (task_data['ma_ok'] == False).any() and (task_data['bs_ok'] == True).all():
                        task_colors.append('red')     # есть p с недопустимым MA и ни одного p с недопустимым bs
                    elif (task_data['bs_ok'] == False).any() and (task_data['ma_ok'] == True).all():
                        task_colors.append('green')   # есть p с недопустимым baseline
                    elif (task_data['both_ok'] == False).any():
                        # Смешанный случай: для разных p разные нарушения – назначим оранжевый для простоты
                        task_colors.append('orange')
                    else:
                        task_colors.append('black')
                color_xticklabels(ax, task_colors)

            # Аннотация со средними по both_ok
            text_lines = []
            for p_val in P_VALUES:
                sub_p = all_data[all_data['p'] == p_val]
                if not sub_p.empty:
                    both_ok_mask = sub_p['both_ok']
                    if both_ok_mask.any():
                        mean_val = sub_p.loc[both_ok_mask, col].mean()
                        cnt = both_ok_mask.sum()
                        text_lines.append(f'p={p_val}: {mean_val:.1f}% (Карт: {cnt})')
                    else:
                        text_lines.append(f'p={p_val}: нет карт с выполнением у обоих')
            plt.annotate('\n'.join(text_lines), xy=(0.98, 0.02), xycoords='axes fraction',
                         ha='right', va='bottom', fontsize=8,
                         bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))

            # Легенда цветов
            color_legend = (
                "Цвет подписи задачи:\n"
                "чёрный – оба метода допустимы\n"
                "красный – только MA недопустим\n"
                "зелёный – только Baseline недопустим\n"
                "оранжевый – оба недопустимы"
            )
            plt.annotate(color_legend, xy=(1.02, 0.5), xycoords='axes fraction',
                         ha='left', va='center', fontsize=8,
                         bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))

            plt.tight_layout()
            plt.savefig(os.path.join(OUTPUT_DIR, f'{ds}_rel_{name}.png'), dpi=150)
            plt.close()

        # ------------------- 3. Столбчатые диаграммы для количества агентов (абсолютные значения) -------------------
        for p_val in P_VALUES:
            sub = all_data[all_data['p'] == p_val]
            if sub.empty:
                continue
            tasks = sub['task'].values
            x = np.arange(len(tasks))
            width = 0.35
            fig, ax = plt.subplots(figsize=(12, 5))
            bars1 = ax.bar(x - width/2, sub['feasible_agents_num_baseline'], width, label='Baseline (TDTSP)', color='salmon')
            bars2 = ax.bar(x + width/2, sub['feasible_agents_num_ma'], width, label='MA', color='steelblue')
            ax.set_xlabel('Инстанс')
            ax.set_ylabel('feasible_agents_num')
            ax.set_title(f'{ds}, p={p_val}: сравнение количества допустимых агентов (Baseline vs MA)')
            ax.set_xticks(x)
            ax.set_xticklabels(tasks, rotation=45, ha='right')

            # Цвет подписей в соответствии со статусом (для данного p)
            task_colors = sub['task_color'].tolist()
            color_xticklabels(ax, task_colors)

            ax.legend()
            ax.grid(True, axis='y', alpha=0.3)
            for bar in bars1:
                h = bar.get_height()
                ax.annotate(f'{int(h)}', xy=(bar.get_x()+bar.get_width()/2, h), xytext=(0,3), textcoords="offset points", ha='center', va='bottom', fontsize=8)
            for bar in bars2:
                h = bar.get_height()
                ax.annotate(f'{int(h)}', xy=(bar.get_x()+bar.get_width()/2, h), xytext=(0,3), textcoords="offset points", ha='center', va='bottom', fontsize=8)

            # Легенда цветов
            color_legend = (
                "Цвет подписи задачи:\n"
                "чёрный – оба метода допустимы\n"
                "красный – только MA недопустим\n"
                "зелёный – только Baseline недопустим\n"
                "оранжевый – оба недопустимы"
            )
            ax.annotate(color_legend, xy=(1.02, 0.5), xycoords='axes fraction',
                        ha='left', va='center', fontsize=8,
                        bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))

            plt.tight_layout()
            plt.savefig(os.path.join(OUTPUT_DIR, f'{ds}_p{p_val}_agents_compare.png'), dpi=150)
            plt.close()

        # ------------------- 4. Общая картинка: три столбчатых графика (для всех p) -------------------
        fig, axes = plt.subplots(1, 3, figsize=(18, 5), sharey=True)
        for i, p_val in enumerate(P_VALUES):
            sub = all_data[all_data['p'] == p_val]
            if sub.empty:
                axes[i].set_title(f'p={p_val} (нет данных)')
                continue
            tasks = sub['task'].values
            x = np.arange(len(tasks))
            width = 0.35
            axes[i].bar(x - width/2, sub['feasible_agents_num_baseline'], width, label='Baseline', color='salmon')
            axes[i].bar(x + width/2, sub['feasible_agents_num_ma'], width, label='MA', color='steelblue')
            axes[i].set_title(f'p={p_val}')
            axes[i].set_xlabel('Инстанс')
            axes[i].set_ylabel('feasible_agents_num')
            axes[i].set_xticks(x)
            axes[i].set_xticklabels(tasks, rotation=45, ha='right', fontsize=8)
            task_colors = sub['task_color'].tolist()
            color_xticklabels(axes[i], task_colors)
            axes[i].legend()
            axes[i].grid(True, axis='y', alpha=0.3)
        plt.suptitle(f'{ds}: сравнение количества допустимых агентов для всех p\n'
                     f'Цвет подписи: чёрный – оба допустимы, красный – только MA недопустим, '
                     f'зелёный – только Baseline недопустим, оранжевый – оба недопустимы', fontsize=12)
        plt.tight_layout()
        plt.savefig(os.path.join(OUTPUT_DIR, f'{ds}_agents_compare_all_p.png'), dpi=150)
        plt.close()

    print("\n" + "=" * 70)
    print(f"✅ Все графики сохранены в {os.path.abspath(OUTPUT_DIR)}")
    print("=" * 70)

if __name__ == "__main__":
    main()