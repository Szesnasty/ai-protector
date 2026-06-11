"""Harm ML classifier node (A1-harm) — semantic harmful-request detection.

Closes the gap that pattern matching, toxicity and the jailbreak classifier
leave open: direct *requests* for harmful content (weapons, drugs, violence,
hate, CSAM, …) that carry no obvious attack keywords and read as ordinary
questions. Uses IBM ``granite-guardian-3.0-2b`` (Apache-2.0, ungated) as a guard
model that scores the prompt's harm probability.

This is a **heavyweight accuracy layer** (~2 B params, ~0.5–1.5 s/request) — it
is gated behind ``enable_harm_ml`` and only added to balanced/strict/paranoid.
Disable it for latency-critical deployments.

Runs on ``scan_text`` so it also sees A2-deobfuscated variants. Lazy-loaded once
and preloaded at startup (main.py).
"""

from __future__ import annotations

import asyncio
import threading

import structlog

from src.config import get_settings
from src.pipeline.nodes import timed_node
from src.pipeline.state import PipelineState

logger = structlog.get_logger()

_model = None
_tokenizer = None
_yes_id: int | None = None
_no_id: int | None = None
_device = "cpu"
_load_lock = threading.Lock()  # guards lazy init against concurrent first requests
_infer_lock = threading.Lock()  # serializes generate() — a single model is not thread-safe


def get_guard():
    """Load (once) the granite-guardian model + tokenizer. Returns (model, tokenizer)."""
    global _model, _tokenizer, _yes_id, _no_id, _device  # noqa: PLW0603
    if _model is None:
        with _load_lock:
            if _model is None:  # double-checked: another thread may have loaded it
                import torch
                from transformers import AutoModelForCausalLM, AutoTokenizer

                settings = get_settings()
                mid = settings.harm_ml_model
                logger.info("harm_ml_init", model=mid)
                tokenizer = AutoTokenizer.from_pretrained(mid)
                if torch.backends.mps.is_available():
                    _device = "mps"
                    dtype = torch.float16
                elif torch.cuda.is_available():
                    _device = "cuda"
                    dtype = torch.float16
                else:
                    _device = "cpu"
                    dtype = torch.bfloat16  # half the RAM of fp32 for a 2 B model on CPU
                model = AutoModelForCausalLM.from_pretrained(mid, dtype=dtype).to(_device).eval()
                _yes_id = tokenizer.encode("Yes", add_special_tokens=False)[0]
                _no_id = tokenizer.encode("No", add_special_tokens=False)[0]
                _tokenizer = tokenizer
                _model = model  # publish last — other threads only see a fully-initialised model
                logger.info("harm_ml_ready", device=_device)
    return _model, _tokenizer


def reset_guard() -> None:
    """Reset the singleton (for testing)."""
    global _model, _tokenizer  # noqa: PLW0603
    _model = None
    _tokenizer = None


def _harm_probability(text: str) -> float:
    """Return P(harm) from granite-guardian for a single prompt."""
    import torch
    import torch.nn.functional as F

    model, tokenizer = get_guard()
    inputs = tokenizer.apply_chat_template(
        [{"role": "user", "content": text}],
        guardian_config={"risk_name": "harm"},
        add_generation_prompt=True,
        return_tensors="pt",
        return_dict=True,
    ).to(_device)
    # Serialize inference — one model object is not safe under concurrent
    # generate() calls (especially on MPS). Throughput is bounded by the device
    # anyway, so the lock costs nothing real and prevents races/corruption.
    with _infer_lock, torch.no_grad():
        out = model.generate(
            **inputs,
            max_new_tokens=1,
            do_sample=False,
            output_scores=True,
            return_dict_in_generate=True,
            pad_token_id=tokenizer.eos_token_id,
        )
    logits = out.scores[0][0]
    probs = F.softmax(torch.stack([logits[_yes_id], logits[_no_id]]), dim=0)
    return float(probs[0].item())


async def check_harm(text: str) -> tuple[float, bool]:
    """Return (P(harm), flagged) for ``text``. Reusable by the post-LLM path."""
    settings = get_settings()
    prob = await asyncio.wait_for(asyncio.to_thread(_harm_probability, text[:2000]), timeout=settings.scanner_timeout)
    return prob, prob >= settings.harm_ml_threshold


@timed_node("harm_ml")
async def harm_ml_node(state: PipelineState) -> PipelineState:
    """Flag the prompt when the guard model's harm probability clears the threshold."""
    settings = get_settings()
    if settings.harm_ml_mode == "off":
        return state

    text = state.get("scan_text") or state.get("user_message", "")
    if not text:
        return state

    risk_flags: dict = {**state.get("risk_flags", {})}
    scanner_results: dict = {**state.get("scanner_results", {})}
    errors: list[str] = list(state.get("errors", []))
    threshold = (
        state.get("policy_config", {}).get("thresholds", {}).get("harm_ml_threshold", settings.harm_ml_threshold)
    )

    try:
        prob = await asyncio.wait_for(
            asyncio.to_thread(_harm_probability, text[:2000]), timeout=settings.scanner_timeout
        )
        scanner_results["harm_ml"] = {"harm_probability": round(prob, 4)}
        if prob >= threshold:
            risk_flags["harm_ml"] = round(prob, 4)
            logger.warning("harm_ml_flag", harm_probability=round(prob, 4), request_id=state.get("request_id"))
    except TimeoutError:
        errors.append(f"harm_ml: timeout after {settings.scanner_timeout}s")
        logger.error("harm_ml_timeout")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"harm_ml: {exc}")
        logger.error("harm_ml_error", error_type=type(exc).__name__)

    return {**state, "risk_flags": risk_flags, "scanner_results": scanner_results, "errors": errors}
