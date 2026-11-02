# 🎓 QuantumFlex Local AI Operator Training Course
**Target Companion:** `qf` (QuantumFlex Sovereign Neural Companion)  
**Host Engine:** AMD Ryzen AI 5 340 Silicon (`127.0.0.1:11434`)  
**Guiding Invariant:** $0.00 External Cloud Spend • 100% Offline Sovereignty  

Welcome to the **Local AI Operator Training Course**. This guide teaches you how to interact with your local neural companion (`qf`) with the same speed, depth, and fluid iteration you experience when pairing with top-tier AI assistants.

---

## 🧭 The Core Mindset: From "Search Engine" to "Co-Pilot"

| Legacy / Search Mindset ❌ | Sovereign Co-Pilot Mindset (`qf`) ✅ |
| :--- | :--- |
| Single disjointed keyword queries ("c11 memory leaks") | Conversational context ("Here's my C11 struct. Walk me through potential leak vectors under fail-closed recovery.") |
| Starting over when the answer isn't perfect | Iterating across turns ("Good, now add boundary checks for null pointers and format it for Paris EVM.") |
| Pasting huge files manually | Using native slash commands (`/view <file>`, `/run <cmd>`) to pull real system state directly into context |
| Trusting unverified output | Demanding grounded citations and testing live with `/athena` and `/run` |

---

## 📚 Module 1: The First Contact & Natural Prompting

### Concept: Speak Directly, Demand Step-by-Step Logic
Your local model (`qwen2.5-coder:7b` or `athena`) thrives when given clear constraints and asked to think step-by-step.

### 🎯 Drill 1: Launch and Ask an Architectural Question
Open a new terminal window and run:
```bash
qf
```
Once the prompt appears (`qf (qwen2.5-coder) >> `), type:
```text
I am designing an edge telemetry consumer that processes incoming JSON packets. 
Give me a 3-step design to handle torn frames without crashing, keeping memory footprint under 50 MB.
```
**Notice:**
* Tokens stream immediately in real time.
* The response is formatted in clean Markdown with clear headings.

---

## 🛠️ Module 2: The Iterative Pair-Programming Loop

### Concept: The "Draft $\rightarrow$ Critique $\rightarrow$ Test" Flow
You never need to get the final code on turn 1. Talk to it like a pair programmer sitting next to you.

### 🎯 Drill 2: Building and Testing a Function Across 3 Turns

#### Turn 1: Initial Draft
```text
Write a pure Python function to compute the SHA-256 Merkle root of an arbitrary list of string payloads.
```

#### Turn 2: Critique & Add Constraints (Follow-up)
Without repeating your prompt, simply type:
```text
Now make it handle an odd number of leaf nodes by duplicating the last node, and add type hints.
```
*(Notice how it remembers the function from Turn 1 and updates only what you asked for!)*

#### Turn 3: Generate the Unit Test
```text
Write a standard pytest test case verifying that an empty list raises ValueError and 3 nodes produce a deterministic 64-character hex digest.
```

---

## 🧠 Module 3: Tapping into Knowledge Memory (`/athena`)

### Concept: Zero-Hallucination Vector Retrieval
Instead of asking general questions from training data, you can query your **actual codebase, specs, and roadmaps** stored inside Athena's vector memory.

### 🎯 Drill 3: Querying the Vault Directly

In your `qf` session, run:
```text
/athena what are the four P0 hard stops?
```
**What happens under the hood:**
1. `qf` queries the local SQLite vector database (`athena_vector_store.db`).
2. It fetches the top 3 verified chunks, prints their source files and SHA-256 provenance hashes.
3. It passes those exact chunks to the local LLM.
4. The LLM answers using **only** your verified system facts.

*Pro-Tip: You can also use automatic keyword detection—any prompt containing words like `roadmap`, `hard stop`, `reserve`, or `invariant` will auto-retrieve Athena context!*

---

## ⚡ Module 4: Agentic Tools (`/run` and `/view`)

### Concept: Feeding Real System State to the Model
Don't guess what the compiler or git tree is saying—let `qf` see it directly.

### 🎯 Drill 4A: Inspecting Code with `/view`
In your `qf` session, type:
```text
/view scripts/qf_companion.py
```
`qf` will ingest the file into conversation memory. Now follow up immediately:
```text
Summarize the main execution loop of this script in 3 concise bullet points.
```

### 🎯 Drill 4B: Running Live System Commands with `/run`
In your `qf` session, type:
```text
/run git status
```
`qf` runs the shell command locally, displays the real output, and loads it into memory. Now follow up:
```text
What files are currently modified or untracked, and are there any security concerns?
```

---

## 🎛️ Module 5: Model Hot-Swapping & Muscle Memory

### Concept: The Right Hammer for the Job

| Model | Size | Strength | When to Use |
| :--- | :--- | :--- | :--- |
| `qwen2.5-coder:7b` | 4.7 GB | Code generation, formal math, system engineering | Writing Solidity, C11, Python, or debugging logic |
| `athena:latest` | 986 MB | High-speed RAG oracle, blunt street wisdom | Blueprint analysis, mission strategy, governance |
| `gemma3:4b` | 3.3 GB | Clean conversational reasoning, document editing | Drafting reports, email drafts, conceptual summaries |
| `amara:latest` | 986 MB | Ultra-fast agentic loop, tool orchestration | Fast JSON formatting, classification, triage |

### 🎯 Drill 5: Switching Models Mid-Flight
In your `qf` session:
```text
/models
```
*(View all loaded models on your host silicon)*

Switch to Athena:
```text
/model athena
```
Now ask:
```text
Give me a blunt sitrep on why sovereign airgapped computing matters for law firms.
```
*(Notice the distinct, sharp persona shift from coder to strategic oracle!)*

---

## 📋 The Essential Operator Cheat Sheet

| Intent | How to Do It |
| :--- | :--- |
| **Start Companion** | `qf` in any terminal |
| **One-Shot Fast Question** | `qf "explain X"` |
| **One-Shot Code Query** | `qf --code "write function Y"` |
| **One-Shot Vault RAG** | `qf --athena "what is policy Z?"` |
| **Check Nodes & RAM** | `/status` inside session, or `qf --status` outside |
| **Run Shell Command** | `/run <command>` (e.g. `/run forge test`) |
| **Read Local File** | `/view <filepath>` |
| **Reset Context** | `/clear` |
| **Save Chat to Markdown** | `/save my_session.md` |
| **Exit** | `/exit` or `Ctrl+D` |
