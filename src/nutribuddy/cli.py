"""The ``nutribuddy`` command."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from . import DISCLAIMER
from .config import ConfigError, Settings
from .documents import SourceError
from .evaluation import run_all
from .index import IndexNotReady
from .ingest import build_index, load_food_folders
from .planner import PlanUnavailable
from .render import plan_to_text
from .safety import InputError
from .service import NutriBuddy
from .sessions import SessionNotFound
from .synthetic import write_all


def _settings(args) -> Settings:
    s = Settings.from_env()
    return s.with_dirs(Path(args.data_dir) if args.data_dir else None, Path(args.work_dir) if args.work_dir else None)


def cmd_synth(args) -> int:
    out = write_all(Path(args.out), seed=args.seed)
    print(f"wrote synthetic documents, food CSV files and evaluation sets to {out}")
    return 0


def cmd_load_foods(args) -> int:
    s = _settings(args)
    rep = load_food_folders(s, Path(args.fdc_dir))
    print(f"food store {s.food_db}: {rep.nutrients} nutrients, {rep.foods} foods, {rep.amounts} amounts "
          f"upserted, {rep.skipped_rows} rows skipped")
    return 0


def cmd_index(args) -> int:
    s = _settings(args)
    rep = build_index(s)
    print(f"index {rep.folder}: {rep.sources} sources, {rep.pages} pages, {rep.chunks} chunks, embedder {rep.embedder}")
    if rep.unregistered:
        print(f"warning: {len(rep.unregistered)} files have no entry in sources.json and are not indexed")
    return 0


def cmd_screen(args) -> int:
    bot = NutriBuddy.from_settings(_settings(args))
    res = bot.screen(args.symptoms)
    if args.json:
        print(json.dumps(res.to_dict(), indent=2))
        return 0
    print(f"status: {res.status}")
    print(res.message)
    for n, h in enumerate(res.hits, start=1):
        print(f"  [{n}] {h.chunk.citation()}")
    print(DISCLAIMER)
    return 0


def cmd_plan(args) -> int:
    bot = NutriBuddy.from_settings(_settings(args))
    plan = bot.plan(args.condition, session_id=args.session)
    print(json.dumps(plan.to_dict(), indent=2) if args.json else plan_to_text(plan))
    return 0


def cmd_session(args) -> int:
    bot = NutriBuddy.from_settings(_settings(args))
    print(bot.new_session(args.condition))
    return 0


def cmd_ask(args) -> int:
    bot = NutriBuddy.from_settings(_settings(args))
    ans = bot.ask(args.session, args.question)
    if args.json:
        print(json.dumps(ans.to_dict(), indent=2))
        return 0
    print(ans.text)
    for s in ans.sources:
        print(f"  {s}")
    return 0


def cmd_eval(args) -> int:
    s = _settings(args)
    bot = NutriBuddy.from_settings(s)
    report = run_all(bot, Path(args.eval_dir) if args.eval_dir else s.data_dir / "eval")
    text = json.dumps(report, indent=2)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 0


def cmd_demo(args) -> int:
    base = Settings.from_env()
    work = Path(args.work_dir or base.work_dir) / "demo"
    s = base.with_dirs(work / "data", work)
    write_all(s.data_dir)
    load_food_folders(s, s.data_dir / "food_data")
    rep = build_index(s)
    print(f"[demo] synthetic data in {s.data_dir}, {rep.chunks} chunks indexed, offline chat model\n")
    bot = NutriBuddy.from_settings(s)
    symptoms = "I am always thirsty, I urinate a lot at night and small cuts heal slowly."
    res = bot.screen(symptoms)
    print(f"[screen] {symptoms}\n  status={res.status} condition={res.condition.value if res.condition else None}")
    print(f"  {res.message}\n")
    sid = bot.new_session()
    plan = bot.plan(res.condition or "diabetes", session_id=sid)
    print("[plan]\n" + plan_to_text(plan) + "\n")
    question = "Which drinks raise blood glucose quickly?"
    ans = bot.ask(sid, question)
    print(f"[ask] {question}\n  {ans.text}")
    for line in ans.sources:
        print(f"  {line}")
    return 0


def cmd_serve(args) -> int:  # pragma: no cover - needs the optional "api" extra
    try:
        import uvicorn
    except ImportError:
        print("install the extra: pip install 'nutribuddy[api]'", file=sys.stderr)
        return 2
    from .api import create_app

    uvicorn.run(create_app(NutriBuddy.from_settings(_settings(args))), host=args.host, port=args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="nutribuddy", description="Cited diet plans for diabetes, heart and thyroid conditions.")
    p.add_argument("--data-dir", help="data folder (default: NUTRIBUDDY_DATA_DIR or ./data)")
    p.add_argument("--work-dir", help="index and store folder (default: NUTRIBUDDY_WORK_DIR or ./.nutribuddy)")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("synth", help="write synthetic demo data")
    sp.add_argument("--out", default="data/synthetic")
    sp.add_argument("--seed", type=int, default=7)
    sp.set_defaults(func=cmd_synth)

    sp = sub.add_parser("load-foods", help="load FoodData Central CSV files into the food store")
    sp.add_argument("--fdc-dir", required=True)
    sp.set_defaults(func=cmd_load_foods)

    sub.add_parser("index", help="build the search index from sources.json").set_defaults(func=cmd_index)

    sp = sub.add_parser("screen", help="screen a symptom description")
    sp.add_argument("symptoms")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_screen)

    sp = sub.add_parser("plan", help="write a cited diet plan for a condition")
    sp.add_argument("condition", help="diabetes, heart or thyroid")
    sp.add_argument("--session")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_plan)

    sp = sub.add_parser("session", help="start a conversation and print its id")
    sp.add_argument("--condition")
    sp.set_defaults(func=cmd_session)

    sp = sub.add_parser("ask", help="ask a follow-up question in a session")
    sp.add_argument("session")
    sp.add_argument("question")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_ask)

    sp = sub.add_parser("eval", help="run the evaluation sets")
    sp.add_argument("--eval-dir")
    sp.add_argument("--out")
    sp.set_defaults(func=cmd_eval)

    sub.add_parser("demo", help="offline end-to-end demo on synthetic data").set_defaults(func=cmd_demo)

    sp = sub.add_parser("serve", help="start the JSON API and the web page (extra: api)")
    sp.add_argument("--host", default="127.0.0.1")
    sp.add_argument("--port", type=int, default=8000)
    sp.set_defaults(func=cmd_serve)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    try:
        return args.func(args)
    except (ConfigError, SourceError, IndexNotReady, InputError, PlanUnavailable, FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except SessionNotFound as exc:
        print(f"error: unknown session {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
