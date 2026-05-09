#!/usr/bin/env python3
"""
Сравнение результатов Multi-Agent-VRP (run_ma_benchmark.py) и TDTSP-PD (run_tdtsp_benchmark.py)
по CSV в experiments/ma_benchmark и experiments/tdtsp_benchmark.

Зависимости: pip install pandas matplotlib  (опционально seaborn для KDE)

Пример:
  python3 scripts/compare_ma_tdtsp_benchmarks.py \\
    --ma-dir experiments/ma_benchmark \\
    --tdtsp-dir experiments/tdtsp_benchmark \\
    --output-dir experiments/compare_ma_tdtsp \\
    --map A

Для диплома: объединение по (map, instance_stem, variant, p); map/p/stem восстанавливаются из json_path.
Графики: score, расстояние; время и after_iterative — только если столбцы есть в CSV.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    import seaborn as sns

    _HAS_SNS = True
except ImportError:
    _HAS_SNS = False

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from run_tdtsp_benchmark import (  # noqa: E402
    instance_join_key_from_json_path,
    map_name_from_json_path,
    p_value_from_json_path,
)

MERGE_KEYS = ["map", "instance_stem", "variant", "p"]


def load_benchmark_csvs(directory: Path, label: str) -> pd.DataFrame:
    paths = sorted(directory.glob("*.csv"))
    if not paths:
        return pd.DataFrame()
    frames = []
    for p in paths:
        df = pd.read_csv(p)
        df["_source_csv"] = p.name
        frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    out["_bench"] = label
    return enrich_benchmark_rows(out)


def enrich_benchmark_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Добавляет map, p, instance_stem, p_percent_tag из json_path; total_score как алиас sum_score."""
    if df.empty or "json_path" not in df.columns:
        return df
    out = df.copy()
    jp = out["json_path"].astype(str)
    out["map"] = jp.map(map_name_from_json_path)
    out["p"] = pd.to_numeric(jp.map(p_value_from_json_path), errors="coerce")
    out["instance_stem"] = jp.map(instance_join_key_from_json_path)

    def _pct_tag(x: object) -> str:
        if pd.isna(x):
            return ""
        try:
            return str(int(round(float(x) * 100)))
        except (TypeError, ValueError):
            return ""

    out["p_percent_tag"] = out["p"].map(_pct_tag)
    if "sum_score" in out.columns:
        out["total_score"] = pd.to_numeric(out["sum_score"], errors="coerce")
    elif "total_score" in out.columns:
        out["sum_score"] = pd.to_numeric(out["total_score"], errors="coerce")
    return out


def numeric_merged(df: pd.DataFrame) -> pd.DataFrame:
    """Приводит суффиксные числовые столбцы к float для графиков."""
    for col in df.columns:
        if col.endswith("_ma") or col.endswith("_tdtsp"):
            if col.startswith(
                (
                    "total_score",
                    "sum_score",
                    "sum_time",
                    "sum_distance",
                    "elapsed_sec",
                    "points_count",
                    "agents_count",
                    "feasible_agents_num",
                    "after_",
                )
            ):
                df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _score_col_ma(m: pd.DataFrame) -> pd.Series:
    if "sum_score_ma" in m.columns:
        return pd.to_numeric(m["sum_score_ma"], errors="coerce")
    return pd.to_numeric(m["total_score_ma"], errors="coerce")


def _score_col_td(m: pd.DataFrame) -> pd.Series:
    if "sum_score_tdtsp" in m.columns:
        return pd.to_numeric(m["sum_score_tdtsp"], errors="coerce")
    return pd.to_numeric(m["total_score_tdtsp"], errors="coerce")


def plot_scatter_score(ax, m: pd.DataFrame) -> None:
    x = _score_col_td(m)
    y = _score_col_ma(m)
    c = m["p_percent_tag"].astype(str)
    if _HAS_SNS:
        sns.scatterplot(x=x, y=y, hue=c, ax=ax, alpha=0.85, s=42)
    else:
        tags = sorted(c.unique())
        for i, t in enumerate(tags):
            mask = c == t
            ax.scatter(x[mask], y[mask], label=str(t), alpha=0.85, s=42, color=f"C{i % 10}")
        ax.legend(title="p%", fontsize=8)
    lims = [
        np.nanmin([x.min(), y.min()]),
        np.nanmax([x.max(), y.max()]),
    ]
    if np.isfinite(lims[0]) and np.isfinite(lims[1]):
        ax.plot(lims, lims, "k--", alpha=0.35, lw=1, label="y=x")
    ax.set_xlabel("TDTSP-PD sum_score")
    ax.set_ylabel("Multi-Agent sum_score")
    ax.set_title("Сопоставление целевого показателя (одинаковые инстансы)")


def plot_paired_diff_score(ax, m: pd.DataFrame) -> None:
    d = _score_col_ma(m) - _score_col_td(m)
    order = sorted(m["p_percent_tag"].dropna().unique(), key=lambda x: float(x))
    data = [d[m["p_percent_tag"] == tag].values for tag in order]
    ax.boxplot(data, tick_labels=[str(x) for x in order], showmeans=True)
    ax.axhline(0, color="k", ls="--", alpha=0.4)
    ax.set_xlabel("p (% в имени набора)")
    ax.set_ylabel("Δ score (MA − TDTSP)")
    ax.set_title("Парная разность качества по уровням p")


def plot_runtime(ax, m: pd.DataFrame) -> None:
    if "elapsed_sec_ma" not in m.columns or "elapsed_sec_tdtsp" not in m.columns:
        ax.text(0.5, 0.5, "нет столбцов elapsed_sec в CSV", ha="center", va="center")
        ax.set_axis_off()
        return
    melted = m.melt(
        id_vars=["p_percent_tag"],
        value_vars=["elapsed_sec_ma", "elapsed_sec_tdtsp"],
        var_name="method",
        value_name="elapsed_sec",
    )
    melted["method"] = melted["method"].map(
        {"elapsed_sec_ma": "Multi-Agent", "elapsed_sec_tdtsp": "TDTSP-PD"}
    )
    melted["elapsed_sec"] = pd.to_numeric(melted["elapsed_sec"], errors="coerce")
    if _HAS_SNS:
        sns.boxplot(
            data=melted,
            x="p_percent_tag",
            y="elapsed_sec",
            hue="method",
            ax=ax,
        )
    else:
        tags = sorted(melted["p_percent_tag"].dropna().unique(), key=lambda x: float(x))
        pos = np.arange(len(tags))
        w = 0.35
        for i, (name, col) in enumerate(
            [("Multi-Agent", "elapsed_sec_ma"), ("TDTSP-PD", "elapsed_sec_tdtsp")]
        ):
            vals = [
                pd.to_numeric(m.loc[m["p_percent_tag"] == t, col], errors="coerce").values
                for t in tags
            ]
            ax.boxplot(
                vals,
                positions=pos + (i - 0.5) * w,
                widths=w * 0.9,
                manage_ticks=False,
            )
        ax.set_xticks(pos)
        ax.set_xticklabels([str(t) for t in tags])
        ax.legend(
            [plt.Rectangle((0, 0), 1, 1, fc="C0"), plt.Rectangle((0, 0), 1, 1, fc="C1")],
            ["Multi-Agent", "TDTSP-PD"],
        )
    ax.set_xlabel("p (% )")
    ax.set_ylabel("elapsed_sec")
    ax.set_title("Время прогона бинарника")


def _bool_mean(series: pd.Series) -> float:
    def to_b(x: object) -> bool:
        if pd.isna(x) or x == "":
            return False
        if isinstance(x, (bool, np.bool_)):
            return bool(x)
        return str(x).strip().lower() in ("true", "1", "yes")

    return float(series.map(to_b).mean())


def plot_success_rates(ax, m: pd.DataFrame) -> None:
    tags = sorted(m["p_percent_tag"].dropna().unique(), key=lambda x: float(x))
    ma_r, td_r = [], []
    for t in tags:
        sub = m[m["p_percent_tag"] == t]
        if "after_iterative_launch_ok_ma" in m.columns:
            ma_r.append(_bool_mean(sub["after_iterative_launch_ok_ma"]))
            td_r.append(_bool_mean(sub["after_iterative_launch_ok_tdtsp"]))
        else:
            ma_r.append(
                float((pd.to_numeric(sub["feasible_agents_num_ma"], errors="coerce").fillna(0) > 0).mean())
            )
            td_r.append(
                float((pd.to_numeric(sub["feasible_agents_num_tdtsp"], errors="coerce").fillna(0) > 0).mean())
            )
    x = np.arange(len(tags))
    w = 0.35
    ax.bar(x - w / 2, ma_r, width=w, label="Multi-Agent", alpha=0.85)
    ax.bar(x + w / 2, td_r, width=w, label="TDTSP-PD", alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels([str(t) for t in tags])
    ax.set_ylim(0, 1.05)
    ax.set_ylabel(
        "доля успешных (after_iterative) или feasible_agents_num>0"
    )
    ax.set_xlabel("p (% )")
    ax.set_title("Успешность итеративного построения маршрутов")
    ax.legend()


def plot_correlation_heatmap(fig, ax, m: pd.DataFrame) -> None:
    cols = [
        "sum_score_ma",
        "sum_score_tdtsp",
        "total_score_ma",
        "total_score_tdtsp",
        "elapsed_sec_ma",
        "elapsed_sec_tdtsp",
        "sum_distance_ma",
        "sum_distance_tdtsp",
        "agents_count_ma",
        "points_count_ma",
    ]
    present = [c for c in cols if c in m.columns]
    if len(present) < 2:
        ax.text(0.5, 0.5, "мало столбцов", ha="center")
        return
    sub = m[present].apply(pd.to_numeric, errors="coerce")
    corr = sub.corr()
    im = ax.imshow(corr.values, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
    ax.set_xticks(range(len(corr.columns)))
    ax.set_yticks(range(len(corr.columns)))
    ax.set_xticklabels(corr.columns, rotation=75, ha="right", fontsize=7)
    ax.set_yticklabels(corr.columns, fontsize=7)
    fig.colorbar(im, ax=ax, fraction=0.046)
    ax.set_title("Корреляция признаков (парные инстансы)")


def write_summary_md(path: Path, m: pd.DataFrame, merged_all: pd.DataFrame) -> None:
    lines = [
        "# Сводка сравнения MA vs TDTSP-PD\n",
        f"- Пар сопоставимых инстансов: **{len(m)}**",
        f"- Строк только в MA: **{int((merged_all['_merge'] == 'left_only').sum())}**",
        f"- Строк только в TDTSP: **{int((merged_all['_merge'] == 'right_only').sum())}**",
        "",
        "## Средние по методам (только пары)",
        "",
    ]
    if len(m):
        for col in ["sum_score", "total_score", "elapsed_sec", "sum_distance"]:
            cma, ctd = f"{col}_ma", f"{col}_tdtsp"
            if cma not in m.columns or ctd not in m.columns:
                continue
            a = pd.to_numeric(m[cma], errors="coerce").mean()
            b = pd.to_numeric(m[ctd], errors="coerce").mean()
            lines.append(f"- **{col}**: MA mean={a:.4g}, TDTSP mean={b:.4g}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Сравнение CSV ma_benchmark vs tdtsp_benchmark (графики для диплома)."
    )
    ap.add_argument("--ma-dir", type=Path, required=True)
    ap.add_argument("--tdtsp-dir", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--map", type=str, default=None, help="Фильтр по столбцу map")
    ap.add_argument("--variant", type=str, default=None, choices=("demand", "unit"))
    args = ap.parse_args()

    ma = load_benchmark_csvs(args.ma_dir, "ma")
    td = load_benchmark_csvs(args.tdtsp_dir, "tdtsp")
    if ma.empty:
        print(f"Нет CSV в {args.ma_dir}", file=sys.stderr)
        return 1
    if td.empty:
        print(f"Нет CSV в {args.tdtsp_dir}", file=sys.stderr)
        return 1

    if args.map:
        ma = ma[ma["map"] == args.map]
        td = td[td["map"] == args.map]
    if args.variant:
        ma = ma[ma["variant"] == args.variant]
        td = td[td["variant"] == args.variant]

    merged = pd.merge(
        ma,
        td,
        on=MERGE_KEYS,
        how="outer",
        indicator=True,
        suffixes=("_ma", "_tdtsp"),
    )
    paired = merged[merged["_merge"] == "both"].copy()
    paired = numeric_merged(paired)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_summary_md(args.output_dir / "summary.md", paired, merged)

    if paired.empty:
        print(
            "Нет пересечения по ключам "
            f"{MERGE_KEYS}. Проверьте, что для одной карты есть оба бенчмарка.",
            file=sys.stderr,
        )
        merged.to_csv(args.output_dir / "merged_outer.csv", index=False)
        return 0

    paired.to_csv(args.output_dir / "merged_paired.csv", index=False)

    # Фигуры
    fig, ax = plt.subplots(figsize=(7, 6))
    plot_scatter_score(ax, paired)
    fig.tight_layout()
    fig.savefig(args.output_dir / "fig1_scatter_total_score.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    plot_paired_diff_score(ax, paired)
    fig.tight_layout()
    fig.savefig(args.output_dir / "fig2_paired_diff_score.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 4.5))
    plot_runtime(ax, paired)
    fig.tight_layout()
    fig.savefig(args.output_dir / "fig3_elapsed_boxplot.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    if "after_iterative_launch_ok_ma" in paired.columns or "feasible_agents_num_ma" in paired.columns:
        plot_success_rates(ax, paired)
    else:
        ax.text(0.5, 0.5, "нет данных для доли успешных", ha="center", va="center")
        ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(args.output_dir / "fig4_success_rates.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 6))
    plot_correlation_heatmap(fig, ax, paired)
    fig.tight_layout()
    fig.savefig(args.output_dir / "fig5_correlation_heatmap.png", dpi=160)
    plt.close(fig)

    print(f"OK → {args.output_dir}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
