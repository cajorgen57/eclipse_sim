from __future__ import annotations
import argparse, sys, time, copy
from typing import Any, Dict, List

from .config import load_configs, env_overrides, apply_cli_overrides
from .reports.run_report import build_run_report
from .value.features import extract_features
from .opponents import analyze_state
from .planners.mcts_pw import PW_MCTSPlanner

# We reuse main.build_state_from_args if available
from . import main as main_mod


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="python -m eclipse_ai.cli",
        description="Eclipse AI CLI"
    )
    sub = p.add_subparsers(dest="cmd")  # avoid required=True for Py<3.7

    # plan
    pl = sub.add_parser("plan", help="Run a planner once and emit a report")
    _add_common_args(pl)
    pl.add_argument("--report", type=str, default=None, help="Path to save report (.json or .md)")
    pl.add_argument("--config", type=str, action="append", default=[], help="YAML/JSON config files (merged)")
    pl.add_argument("--env-prefix", type=str, default="ECLIPSE_AI__", help="Env prefix for overrides")
    pl.add_argument("--print-md", action="store_true", help="Print Markdown report to stdout")

    # bench
    bn = sub.add_parser("bench", help="Run multiple seeds to measure stability/perf")
    _add_common_args(bn)
    bn.add_argument("--seeds", type=int, default=8, help="Number of seeds")
    bn.add_argument("--config", type=str, action="append", default=[], help="YAML/JSON config files (merged)")
    bn.add_argument("--env-prefix", type=str, default="ECLIPSE_AI__", help="Env prefix for overrides")
    bn.add_argument("--out", type=str, default=None, help="Save benchmark JSON")

    args = p.parse_args(argv)
    if getattr(args, "cmd", None) is None:
        p.print_help()
        sys.exit(2)
    return args


def _add_common_args(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--planner", choices=["legacy", "pw_mcts"], default="pw_mcts",
                    help="Planner backend (legacy is deprecated, use pw_mcts)")
    ap.add_argument("--sims", type=int, default=200)
    ap.add_argument("--depth", type=int, default=2)
    ap.add_argument("--pw-alpha", dest="pw_alpha", type=float, default=0.6)
    ap.add_argument("--pw-c", dest="pw_c", type=float, default=1.5)
    ap.add_argument("--prior-scale", type=float, default=0.5)
    ap.add_argument("--determinization", type=int, default=0)
    ap.add_argument("--rollout-len", type=int, default=3)
    ap.add_argument("--opponent-awareness", action="store_true", help="Enable opponent-aware priors/eval")
    ap.add_argument("--weights", type=str, default=None)
    ap.add_argument("--seed", type=int, default=0)
    # Your state inputs:
    ap.add_argument("--board", type=str, default=None)
    ap.add_argument("--tech", type=str, default=None)


def _build_state(args: argparse.Namespace):
    # Delegate to repo's main if it exposes a builder; else fail with guidance
    if hasattr(main_mod, "build_state_from_args"):
        return main_mod.build_state_from_args(args)
    raise RuntimeError("build_state_from_args not found; add it to eclipse_ai/main.py (see earlier instructions).")


def _opponent_context(state: Any, enabled: bool, seed: int):
    if not enabled:
        return None, None, None
    rd = getattr(state, "round_index", 0)
    me = getattr(state, "active_player_id", 0)
    models, tmap = analyze_state(state, my_id=me, round_idx=rd)
    feats = extract_features(state, context=None)
    return models, tmap, feats


def _apply_cfg_env(args: argparse.Namespace) -> None:
    """Optional: layer config/env into args. Extend as you add keys."""
    # NOTE: Currently we only parse the files/env; we don't override args fields.
    # If you want this, uncomment and map keys appropriately.
    # cfg = load_configs(getattr(args, "config", []))
    # cfg = apply_cli_overrides(cfg, env_overrides(getattr(args, "env_prefix", "ECLIPSE_AI__")))
    # for key, val in (cfg.get("planner", {}) or {}).items():
    #     attr = key.replace("-", "_")
    #     if hasattr(args, attr):
    #         setattr(args, attr, val)
    # Currently no-op - config/env override not implemented
    pass


def _plan_once(args: argparse.Namespace) -> Dict[str, Any]:
    _apply_cfg_env(args)

    # Build state
    state = _build_state(args)

    # Legacy path
    if args.planner == "legacy":
        if hasattr(main_mod, "run_legacy_planner"):
            ranked = main_mod.run_legacy_planner(args, state)
            return {"ranked": ranked, "report": None}
        raise RuntimeError("Legacy planner path not wired; set --planner pw_mcts")

    # PW‑MCTS
    planner = PW_MCTSPlanner(
        pw_c=args.pw_c, pw_alpha=args.pw_alpha, prior_scale=args.prior_scale,
        sims=args.sims, depth=args.depth, seed=args.seed
    )
    planner.opponent_awareness = bool(args.opponent_awareness)
    if hasattr(planner, "determinization"):
        planner.determinization = int(args.determinization)
    if hasattr(planner, "rollout_len"):
        planner.rollout_len = int(args.rollout_len)

    # Optional: context for reporting (planner may compute its own context internally)
    models, tmap, feats = _opponent_context(state, planner.opponent_awareness, args.seed)

    # Run plan with diagnostics if available; else fall back gracefully
    try:
        ranked, diag = planner.plan_with_diagnostics(state)
    except AttributeError:
        ranked = planner.plan(state)
        di_children = []
        for mac in (ranked or []):
            di_children.append({
                "type": getattr(mac, "type", "?"),
                "prior": float(getattr(mac, "prior", 0.0)),
                "visits": 0,
                "mean_value": 0.0,
                "payload": dict(getattr(mac, "payload", {})),
            })
        diag = {
            "children": di_children,
            "sims": args.sims,
            "depth": args.depth,
            "seed": args.seed,
            "params": {"pw_alpha": args.pw_alpha, "pw_c": args.pw_c, "prior_scale": args.prior_scale},
        }

    # Build report
    report = build_run_report(
        planner_name="pw_mcts",
        params=diag.get("params", {}),
        seed=args.seed,
        determinization=int(getattr(args, "determinization", 0)),
        sims=args.sims,
        depth=args.depth,
        child_stats=diag.get("children", []),
        opponent_models=models,
        threat_map=tmap,
        features_snapshot=feats
    )
    return {"ranked": ranked, "report": report}


def _bench(args: argparse.Namespace) -> Dict[str, Any]:
    seeds = int(args.seeds)
    base_state = _build_state(args)
    top_keys: List[tuple] = []
    values: List[float] = []
    t0 = time.perf_counter()

    for s in range(seeds):
        # fresh copy per seed to avoid accidental mutations
        state = copy.deepcopy(base_state)

        planner = PW_MCTSPlanner(
            pw_c=args.pw_c, pw_alpha=args.pw_alpha, prior_scale=args.prior_scale,
            sims=args.sims, depth=args.depth, seed=s
        )
        planner.opponent_awareness = bool(args.opponent_awareness)
        if hasattr(planner, "determinization"):
            planner.determinization = int(args.determinization)
        if hasattr(planner, "rollout_len"):
            planner.rollout_len = int(args.rollout_len)

        try:
            ranked, diag = planner.plan_with_diagnostics(state)
        except AttributeError:
            ranked = planner.plan(state)
            diag = {"children": []}

        if ranked:
            mac = ranked[0]
            key = (
                getattr(mac, "type", "?"),
                tuple(sorted((k, v) for k, v in mac.payload.items() if not str(k).startswith("__")))
            )
            top_keys.append(key)
            mv = float(diag["children"][0]["mean_value"]) if diag.get("children") else 0.0
            values.append(mv)

    t1 = time.perf_counter()
    sims_total = seeds * args.sims
    elapsed = max(1e-9, t1 - t0)

    if not top_keys:
        stab = 0.0
    else:
        mode = max(set(top_keys), key=top_keys.count)
        stab = top_keys.count(mode) / len(top_keys)

    return {
        "seeds": seeds,
        "stability_top1": stab,
        "mean_value": sum(values)/len(values) if values else 0.0,
        "sims": args.sims,
        "depth": args.depth,
        "sims_per_sec": sims_total / elapsed
    }


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.cmd == "plan":
        res = _plan_once(args)
        report = res.get("report")
        if report:
            if args.report:
                if args.report.endswith(".json"):
                    with open(args.report, "w", encoding="utf-8") as f:
                        f.write(report.to_json())
                elif args.report.endswith(".md"):
                    with open(args.report, "w", encoding="utf-8") as f:
                        f.write(report.to_markdown())
                else:
                    print("Report path must end with .json or .md", file=sys.stderr)
            if args.print_md:
                print(report.to_markdown())
        else:
            ranked = res.get("ranked") or []
            for i, mac in enumerate(ranked[:3], 1):
                print(f"{i}. {getattr(mac,'type','?')}  payload={getattr(mac,'payload',{})}")
        return 0

    if args.cmd == "bench":
        out = _bench(args)
        if args.out:
            import json
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump(out, f, indent=2)
        print(out)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
