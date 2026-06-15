"""One-off: record AI Protector (harm mode) per-attack BLOCK/ALLOW by id, so we
can compute the real defense-in-depth (protector + each OpenAI model) leak rate.
Writes {id: bool blocked} to results/protector_harm_decisions.json."""

import asyncio
import json
import os

os.environ.setdefault("MODE", "demo")
os.environ["HARM_ML_MODE"] = "pre_llm"

from benchmarks.common import RESULTS_DIR, build_pre_llm_pipeline, make_state  # noqa: E402
from benchmarks.external.schema import load_corpus  # noqa: E402
from src.config import get_settings  # noqa: E402

get_settings.cache_clear()


async def main() -> None:
    attacks = [r for r in load_corpus(surface="proxy") if r.expected != "ALLOW"]
    pipe = build_pre_llm_pipeline()
    await pipe.ainvoke(make_state("warmup", "balanced"))
    decisions: dict[str, bool] = {}
    for i, rec in enumerate(attacks):
        out = await pipe.ainvoke(make_state(rec.prompt, "balanced"))
        decisions[rec.id] = out.get("decision") in ("BLOCK", "MODIFY")
        if (i + 1) % 100 == 0:
            blocked = sum(decisions.values())
            print(f"  {i + 1}/{len(attacks)}  blocked={blocked}", flush=True)
    out_path = RESULTS_DIR / "protector_harm_decisions.json"
    out_path.write_text(json.dumps(decisions))
    print(f"blocked {sum(decisions.values())}/{len(decisions)} -> {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
