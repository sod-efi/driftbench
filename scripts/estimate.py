"""Print the token volume and the estimated judge cost per model for each split."""

from driftbench import common
from driftbench.judge import OPENROUTER_PRICING, estimate_cost_usd
from driftbench.run import count_prompt_tokens

dev = common.load_dev_split()
rogue = sum(1 for t in dev if t["trajectory_type"] == "rogue")
labelled = sum(1 for t in dev if t.get("rogue_step"))
print(f"dev split: {len(dev)} trajectories, {rogue} rogue ({labelled} with a labelled rogue step)")
hold, _ = common.load_holdout()
prompt = common.read_prompt(common.current_prompt_version())
for name, trajs in [("holdout", hold), ("dev", dev)]:
    tokens, steps = count_prompt_tokens(trajs, prompt)
    print(f"\n{name}: {len(trajs)} trajectories, {steps} steps, {tokens:,} input tokens")
    for model in OPENROUTER_PRICING:
        print(f"   {model:35s} about ${estimate_cost_usd(model, tokens, steps):.2f}")
