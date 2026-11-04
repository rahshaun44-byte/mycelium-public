# Athena Knowledge Domain 05: Machine Learning & Neural Architectures

Domain 05 defines the computational and cognitive foundations of how Athena learns representations, processes natural and scientific language, performs inference, and retrieves knowledge across the sovereign vault.

Together with Domain 06 (Computer Science & Systems Architecture), Domain 05 establishes a locally operated, scientifically grounded, and computationally verifiable intelligence system.

---

## 1. Transformer and Attention Architectures

Athena understands the explicit mathematical mechanisms governing foundation models and attention layers.

### The Scaled Dot-Product Attention Equation
$$\text{Attention}(Q, K, V) = \text{softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right)V$$

Where:
- $Q \in \mathbb{R}^{n \times d_k}$: Query matrix representing active token context.
- $K \in \mathbb{R}^{m \times d_k}$: Key matrix representing addressable memory states.
- $V \in \mathbb{R}^{m \times d_v}$: Value matrix containing token feature representations.
- $d_k$: Scaling dimension preventing gradient vanishing in the softmax exponent.

### Modern Architectural Primitives
| Technology | Architectural Mechanism | Purpose in Sovereign Inference |
| :--- | :--- | :--- |
| **MHA** (Multi-Head Attention) | Projects queries, keys, and values into $h$ subspaces | Allows the model to attend to information from different positions and representation subspaces simultaneously |
| **GQA** (Grouped-Query Attention) | Multiple query heads share a single key-value head group | Drastically reduces KV-cache memory bandwidth, enabling long contexts on AMD Ryzen AI hardware |
| **RoPE** (Rotary Position Embeddings) | Applies rotation matrix to 2D chunks of query/key vectors | Naturally encodes relative token distances and preserves positional invariance across long context spans |
| **MoE** (Mixture-of-Experts) | Dynamically routes tokens to top-$k$ sparse feed-forward experts | Scales parameter capacity while keeping per-token compute and latency strictly bounded |
| **RMSNorm** | Root Mean Square Layer Normalization: $\bar{a}_i = \frac{a_i}{\text{RMS}(a)} g_i$ | Accelerates training convergence and eliminates mean-centering overhead without numerical instability |

---

## 2. Representation Learning and Embeddings

Athena converts textual and scientific assertions into geometric vector representations using Transformer-based embedding architectures.

### Mathematical Formulation
An embedding function maps unstructured semantic information into a fixed $d$-dimensional unit hypersphere:
$$f(x) \to \mathbb{R}^d, \quad \|f(x)\|_2 = 1$$

Pairwise semantic similarity is computed via cosine similarity:
$$\operatorname{sim}(A, B) = \frac{A \cdot B}{\|A\|\|B\|} = \cos(\theta)$$

### Core Representation Techniques
- **Contrastive Learning & InfoNCE Loss**: Maximizes mutual information between positive document-query pairs while pushing negative samples apart on the hypersphere:
  $$\mathcal{L}_{\text{InfoNCE}} = -\log \frac{\exp(\operatorname{sim}(q, k_+) / \tau)}{\sum_{j} \exp(\operatorname{sim}(q, k_j) / \tau)}$$
- **Bi-Encoder Topologies**: Decouples document encoding from runtime query encoding for $O(1)$ offline vector pre-computation.
- **Metric Learning & Normalization**: Guarantees that vector distance directly models semantic relevance.
- **Dimensionality Reduction**: Preserves topological manifolds while minimizing memory footprints.

> [!CRITICAL]
> Cosine similarity measures geometric semantic proximity in vector space, not factual correctness. High similarity between two assertions does not establish that either is true.

---

## 3. Optimization and Training Dynamics

Athena evaluates how models are tuned, quantized, and stabilized for offline local execution.

### Key Optimization Frameworks
- **AdamW**: Adaptive moment estimation with decoupled weight decay ($\theta_{t} = \theta_{t-1} - \eta_t \lambda \theta_{t-1} - \frac{\eta_t}{\sqrt{\hat{v}_t} + \epsilon} \hat{m}_t$), preventing weight degradation in adaptive learning rate regimes.
- **RMSprop**: Normalizes gradient steps by running average of squared gradients.
- **Gradient Clipping**: Enforces $\|\nabla \mathcal{L}\|_2 \le c$, preventing gradient explosion in recurrent and deep transformer topologies.
- **Learning Rate Scheduling**: Cosine annealing with warm restarts for escaping local saddle points.
- **LoRA / QLoRA**: Low-Rank Adaptation factorizing weight updates: $W + \Delta W = W + \frac{\alpha}{r} B A$, where $A \in \mathbb{R}^{r \times k}, B \in \mathbb{R}^{d \times r}$ with rank $r \ll \min(d, k)$. QLoRA introduces NF4 (NormalFloat4) and double quantization to fine-tune on local hardware.
- **Quantization Formats**: GGUF (llama.cpp execution format), AWQ (Activation-aware Weight Quantization), and GPTQ (second-order Hessian error compensation).

---

## 4. Inference & Evidence-Grounded RAG Synthesis

Domain 05 powers Athena's local cognitive loop, anchoring generation to verified ground-truth documents.

### Local RAG Execution Topology
```text
                  User Query
                      │
                      ▼
               Query Processing
                      │
                      ▼
             Embedding Generation
            (nomic-embed-text 768d)
                      │
                      ▼
           Vector Database Retrieval
             (athena_vectors.db)
                      │
                      ▼
               Semantic Ranking
                      │
                      ▼
           Reciprocal Rank Fusion
                      │
                      ▼
             Context Construction
                      │
                      ▼
             Local LLM Inference
          (Ollama athena:latest)
                      │
                      ▼
          Evidence-Grounded Response
```

### Reciprocal Rank Fusion (RRF)
Combines semantic dense vector search with sparse lexical matching (BM25):
$$\operatorname{RRF}(d) = \sum_{i=1}^n \frac{1}{k + \operatorname{rank}_i(d)}$$
Where $k \approx 60$ acts as a smoothing parameter to balance top-heavy rank distributions.

---

## 5. Epistemic Calibration & Epistemic Tiers

Athena maintains explicit separation between cognitive confidence and physical reality:

1. **Model Confidence**: Internal softmax probability across generated tokens.
2. **Retrieval Similarity**: Geometric cosine alignment between query and candidate chunks.
3. **Empirical Evidence Strength**: Number and independence of physical measurements validating a claim.
4. **Mathematical Proof**: Complete derivation verified by a trusted kernel (Lean 4 / Coq).
5. **Factual Correctness**: Objective truth of the statement in physical reality.

> [!IMPORTANT]
> A model can produce a maximally confident answer that is completely incorrect. Model confidence must never be substituted for empirical evidence or mathematical proof.

---

## 6. Architectural Trace Invariant

Every substantive assertion generated by Athena must satisfy the deterministic trace invariant:
$$\boxed{ \text{Claim} \longrightarrow \text{Evidence} \longrightarrow \text{Source} \longrightarrow \text{Validation} }$$

If supporting ground-truth evidence cannot be retrieved from the sovereign vault, Athena explicitly communicates the boundary of knowledge and reports the conclusion as unverified conjecture.
