import sys, json, argparse
sys.path.append("..")  # if running inside eclipse_test within repo root
try:
    from eclipse_ai import recommend
except Exception:
    # fallback: try installed package
    from eclipse_ai import recommend

p = argparse.ArgumentParser()
p.add_argument("--board", default="board.jpg")
p.add_argument("--tech",  default="tech.jpg")
p.add_argument("--sims",  type=int, default=200)
p.add_argument("--depth", type=int, default=2)
p.add_argument("--topk",  type=int, default=5)
args = p.parse_args()

manual = {"_planner":{"simulations":args.sims,"depth":args.depth,"risk_aversion":0.25}}
out = recommend(args.board, args.tech, manual_inputs=manual, top_k=args.topk)
print(json.dumps({
  "round": out.get("round"),
  "active_player": out.get("active_player"),
  "plans": out.get("plans")[:3],   # show top 3
  "enemy_posteriors": out.get("enemy_posteriors", {}),
  "expected_bags": out.get("expected_bags", {})
}, indent=2))
