#!/usr/bin/env python3
"""
Для каждого *.vrp под datasets/ создаёт 4 JSON (как cvrplib_vrp_to_json.py):
  <stem>_ma_demand_K<K>.json, <stem>_ma_unit_K<K>.json,
  <stem>_tdtsp_base_demand.json, <stem>_tdtsp_base_unit.json
  (в tdtsp_base_* поле agents_cnt=K для TDTSP-PD без обязательного -K в CLI)

По умолчанию max_time / max_distance = 2^63-1 (--huge-limits).
K: VEHICLES / шаблон имени …-kN; если не вышло — соседний <stem>.sol (число строк Route #).
С --prefer-sol-agents при наличии .sol K берётся из него в первую очередь.

Пример:
  python3 scripts/build_dataset_json.py --datasets-root datasets/A --out-dir experiments/dataset_json/A

С полосой min/max вершин (как cvrplib_vrp_to_json.py --balance-p):
  python3 scripts/build_dataset_json.py --datasets-root datasets/A --balance-p 0.2
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "scripts"))
    from cvrplib_vrp_to_json import convert_vrp_to_four_jsons, stem_with_balance  # noqa: E402

    ap = argparse.ArgumentParser(
        description="Пакетная конвертация datasets/**/*.vrp в 4 JSON на файл"
    )
    ap.add_argument(
        "--datasets-root",
        type=Path,
        default=repo_root / "datasets",
        help="Корень с подкаталогами A/, B/, … и .vrp",
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=repo_root / "experiments" / "dataset_json",
        help="Куда писать JSON (сохраняется структура подкаталогов)",
    )
    ap.add_argument(
        "--flat",
        action="store_true",
        help="Класть все файлы прямо в out-dir (имена должны быть уникальны)",
    )
    ap.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Обработать не больше N файлов (0 = все)",
    )
    ap.add_argument(
        "--no-huge-limits",
        action="store_true",
        help="Не ставить max_time/max_distance в 2^63-1 (использовать эвристику по матрице)",
    )
    ap.add_argument(
        "--agents",
        "-K",
        type=int,
        default=None,
        help="Переопределить K для всех файлов (иначе из каждого .vrp)",
    )
    ap.add_argument(
        "--prefer-sol-agents",
        action="store_true",
        help="Для каждого .vrp: если рядом есть <stem>.sol, брать K по числу маршрутов (Route #).",
    )
    ap.add_argument(
        "--balance-p",
        type=float,
        default=None,
        metavar="P",
        help="Как в cvrplib_vrp_to_json: полоса ± вокруг μ=|C|/K для min_load/max_load (0 ≤ p < 1).",
    )
    ap.add_argument(
        "--balance-policy",
        choices=("strict", "relax"),
        default="strict",
        help="strict — ошибка при нарушении K·min ≤ |C| ≤ K·max; relax — подправить границы.",
    )
    ap.add_argument(
        "--min-load-tdtsp",
        type=int,
        default=1,
        help="Скаляр min_load для tdtsp_base_*, если не задан --balance-p (см. prepare_tdtsp_instances).",
    )
    ap.add_argument(
        "--balance-report-each",
        action="store_true",
        help="При --balance-p сохранять отчёт в <out>/<stem>_balance_report.json для каждого .vrp",
    )
    ap.add_argument(
        "--add-avg-to-scores",
        action="store_true",
        help="Добавить к point_scores (кроме депо) среднее арифметическое матрицы расстояний (округлённое до целого). Создаются дополнительные *_avg.json файлы.",
    )
    args = ap.parse_args()

    root: Path = args.datasets_root.resolve()
    if not root.is_dir():
        print(f"Нет каталога: {root}", file=sys.stderr)
        return 1

    out_root: Path = args.out_dir.resolve()
    huge = not args.no_huge_limits

    vrp_files = sorted(root.rglob("*.vrp"))
    if args.limit > 0:
        vrp_files = vrp_files[: args.limit]

    ok = 0
    failed: list[tuple[Path, str]] = []

    for vrp in vrp_files:
        if args.flat:
            target_dir = out_root
        else:
            try:
                rel_parent = vrp.parent.relative_to(root)
            except ValueError:
                rel_parent = Path(".")
            target_dir = out_root / rel_parent
        target_dir.mkdir(parents=True, exist_ok=True)

        print(f"=== {vrp.relative_to(root)} -> {target_dir}", file=sys.stderr)
        br: Path | None = None
        if args.balance_report_each and args.balance_p is not None:
            br = target_dir / f"{stem_with_balance(vrp.stem, args.balance_p)}_balance_report.json"
        try:
            rc = convert_vrp_to_four_jsons(
                vrp,
                target_dir,
                stem=vrp.stem,
                agents=args.agents,
                min_load_tdtsp=args.min_load_tdtsp,
                balance_p=args.balance_p,
                balance_policy=args.balance_policy,
                balance_report=br,
                huge_limits=huge,
                prefer_sol_agents=args.prefer_sol_agents,
                add_avg_to_scores=args.add_avg_to_scores
            )
        except Exception as e:
            failed.append((vrp, str(e)))
            print(f"FAIL {vrp}: {e}", file=sys.stderr)
            continue
        if rc != 0:
            failed.append((vrp, f"exit {rc}"))
        else:
            ok += 1

    print(
        f"\nГотово: успешно {ok}, ошибок {len(failed)} из {len(vrp_files)}",
        file=sys.stderr,
    )
    if failed:
        for p, msg in failed[:20]:
            print(f"  {p}: {msg}", file=sys.stderr)
        if len(failed) > 20:
            print(f"  ... и ещё {len(failed) - 20}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
