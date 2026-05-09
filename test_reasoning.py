"""
Test whether reasoning/thinking is disabled for utility calls.

Thinking models like QwQ/Qwen3 emit <think>...</think> blocks before responding.
This script runs the same prompt twice — once with enable_thinking=False and once
without — and checks whether <think> tags appear in the output.
"""

import os, time
os.environ.setdefault("OPENAI_API_BASE", "http://localhost:8080/v1")
os.environ.setdefault("OPENAI_API_KEY", "sk-no-key-needed")

from openai import OpenAI

client = OpenAI(base_url=os.environ["OPENAI_API_BASE"], api_key=os.environ["OPENAI_API_KEY"], timeout=60.0)

PROMPT = (
    "A snail is at the bottom of a 30-foot well. Each day it climbs 3 feet, "
    "but each night it slides back 2 feet. How many days does it take to reach the top? "
    "Think through it step by step."
)

def run(label, extra_body):
    print(f"\n{'='*50}")
    print(f"Test: {label}")
    print(f"extra_body: {extra_body}")
    print(f"{'='*50}")

    t0 = time.time()
    resp = client.chat.completions.create(
        model="local-model",
        messages=[{"role": "user", "content": PROMPT}],
        temperature=0.0,
        max_tokens=1024,
        stream=True,
        extra_body=extra_body or {}
    )

    full_output = ""
    token_count = 0
    for chunk in resp:
        delta = chunk.choices[0].delta if chunk.choices else None
        if delta and delta.content:
            full_output += delta.content
            token_count += 1

    elapsed = time.time() - t0
    has_think_tags = "<think>" in full_output.lower()
    # Also treat 0 content tokens after long wait as "thinking active" —
    # llama.cpp filters thinking tokens from the stream instead of exposing them as <think> tags
    silent_thinking = (token_count == 0 and elapsed > 5.0)

    print(f"Output ({token_count} tokens, {elapsed:.1f}s):")
    preview = full_output[:400] + ("..." if len(full_output) > 400 else "")
    print(preview if full_output else "(no content output)")
    print()
    if has_think_tags:
        print(f">>> <think> tags detected: YES — reasoning is ACTIVE (tags in output)")
    elif silent_thinking:
        print(f">>> <think> tags detected: YES (implied) — reasoning is ACTIVE (silent, {elapsed:.1f}s with 0 content tokens)")
    else:
        print(f">>> <think> tags detected: NO  — reasoning appears DISABLED")
    return has_think_tags or silent_thinking

thinking_on  = run("No extra_body (baseline)",                                   None)
thinking_off = run("chat_template_kwargs enable_thinking=False",                  {"chat_template_kwargs": {"enable_thinking": False}})

print(f"\n{'='*50}")
print("SUMMARY")
print(f"{'='*50}")
if thinking_on and not thinking_off:
    print("[OK]  enable_thinking=False successfully disabled reasoning.")
elif not thinking_on and not thinking_off:
    print("[INFO] No <think> tags in either run. Either the model doesn't support thinking,")
    print("       or reasoning is already disabled at the server level (e.g. --no-context-shift).")
    print("       The extra_body param may be redundant but harmless.")
elif thinking_on and thinking_off:
    print("[FAIL] enable_thinking=False did NOT disable reasoning. Try a different parameter.")
    print("       Check your server docs. You may need: {\"thinking\": {\"type\": \"disabled\"}}")
else:
    print("[WARN] Baseline had no thinking but enable_thinking=False run did -- unexpected.")
