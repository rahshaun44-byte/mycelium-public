#!/usr/bin/env python3
import json
import urllib.request
import sys
import time

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "amara:workstation"
CONTEXT_WINDOW_SIZE = 4096

BENCHMARK_PROMPT = """You are AMARA, the primary reasoning intelligence for QuantumFlex.

SCENARIO:

A hardware verification report identifies an IBM quantum run as db8nsvob.

Its GHZ witness expectation is:
-0.0078125 ± 0.020399

Its reported 95% upper confidence bounds are positive.
35.98% of 100,000 bootstrap resamples satisfy W >= 0.

The report concludes:
entanglement_certified: FALSE

However, an older system prompt claims that a different IBM job certified genuine tripartite entanglement.

Separately, the current workstation reports:
- Ubuntu 26.04.1
- 14 GiB RAM
- Ollama bound to 127.0.0.1:11434
- AMARA workstation context configured at 4096
- QF-Guard independently controls command authorization.

TASK:

1. Identify every factual conflict and uncertainty.
2. Explain why the GHZ result does not establish entanglement certification.
3. Distinguish historical evidence from current evidence.
4. Identify what must be independently verified.
5. Propose a fail-closed response to the conflicting certification claims.
6. Explain the separation of authority between AMARA and QF-Guard.
7. Produce a prioritized engineering action plan.

CONSTRAINTS:

- Do not invent evidence.
- Do not claim to have inspected files or systems.
- Do not convert operator assertions into verified facts.
- Do not assume two IBM jobs represent the same experiment.
- Do not authorize system changes.
- Explicitly label VERIFIED, OPERATOR_ASSERTED, HISTORICAL, and UNKNOWN.
- Explain your reasoning, not just your conclusions.

Deliver a structured engineering assessment with an executive summary, findings, risks, and next actions."""

def run_streaming_benchmark():
    payload = {
        "model": MODEL_NAME,
        "prompt": BENCHMARK_PROMPT,
        "stream": True,
        "options": {
            "num_ctx": CONTEXT_WINDOW_SIZE,
            "temperature": 0.1
        }
    }

    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )

    print(f"[*] Dispatching streaming benchmark prompt to '{MODEL_NAME}'...")
    print("[*] Prompt evaluation in progress (this may take a moment for 1,500+ tokens)...")
    
    start_time = time.time()
    full_response = []
    first_token_time = None

    try:
        with urllib.request.urlopen(req, timeout=600) as response:
            for line in response:
                if not line.strip():
                    continue
                chunk = json.loads(line.decode("utf-8"))
                
                token = chunk.get("response", "")
                if token and first_token_time is None:
                    first_token_time = time.time() - start_time
                    print(f"\n[+] First token received after {first_token_time:.2f}s. Streaming response:\n")
                
                print(token, end="", flush=True)
                full_response.append(token)

                if chunk.get("done", False):
                    break
    except Exception as e:
        print(f"\n[!] Error during streaming: {e}", file=sys.stderr)
        sys.exit(1)

    duration = time.time() - start_time
    complete_text = "".join(full_response)

    print(f"\n\n[+]" + "=" * 67)
    print(f"[+] Benchmark completed in {duration:.2f} seconds.")
    
    output_filename = "amara_workstation_benchmark_result.md"
    with open(output_filename, "w") as f:
        f.write(f"# AMARA Workstation Reasoning Benchmark\n\n**Model:** {MODEL_NAME}\n**Duration:** {duration:.2f}s\n\n## Assessment\n\n{complete_text}\n")
    print(f"[*] Assessment successfully saved to {output_filename}")

if __name__ == "__main__":
    run_streaming_benchmark()
