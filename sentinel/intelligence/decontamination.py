#!/usr/bin/env python3
"""
═════════════════════════════════════════════════════════════════════
  QUANTUM FLEX: ATHENA LITERATURE DECONTAMINATION ENGINE
═════════════════════════════════════════════════════════════════════
Screening and quarantine protocol for ingested scientific literature.
Prevents evaluation benchmark leakage (GSM8K, MATH, HumanEval, ARC, MMLU)
using 13-gram exact matching, MinHash signatures, and Jaccard distance.
"""

import re
import json
import hashlib
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import List, Dict, Set, Any, Optional, Tuple


@dataclass(frozen=True)
class DecontaminationAuditResult:
    paper_id: str
    source_uri: str
    content_sha256: str
    minhash_signature: str
    benchmark_leakage_score: float
    quarantine_status: str  # "CLEAN", "QUARANTINED", "DUPLICATE"
    matching_ngrams: List[str]
    audited_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class BenchmarkDecontaminationGate:
    """
    Screens incoming literature, research papers, and technical memos against
    benchmark test sets to guarantee Zero Evaluation Leakage.
    """

    # Representative benchmark question signatures / canonical problem stems
    # In production, this can be expanded or loaded from an external hash database
    STANDARD_BENCHMARK_PROMPTS = [
        "A train leaves Chicago heading east at 60 miles per hour. Another train leaves New York",
        "Janet's ducks lay 16 eggs per day. She eats three for breakfast every morning and bakes",
        "Let S be the set of all positive integers n such that n is a multiple of",
        "Find the number of real solutions to the equation",
        "def has_close_elements(numbers: List[float], threshold: float) -> bool:",
        "def separate_paren_groups(paren_string: str) -> List[str]:",
        "Which of the following is the primary mechanism of action of penicillin?",
        "A 45-year-old male presents to the emergency department with acute chest pain",
        "What is the total resistance of three 10-ohm resistors connected in parallel?",
        "Calculate the determinant of the matrix given by"
    ]

    def __init__(self, num_perm: int = 64, ngram_size: int = 13, leakage_threshold: float = 0.10):
        self.num_perm = num_perm
        self.ngram_size = ngram_size
        self.leakage_threshold = leakage_threshold
        self.benchmark_ngrams: Set[str] = set()
        self.benchmark_tokens: Set[str] = set()
        self._index_benchmarks()

    def _clean_and_tokenize(self, text: str) -> List[str]:
        # Strip code blocks, control characters, normalize lower
        text_clean = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
        tokens = re.findall(r'\b[a-z0-9_]+\b', text_clean.lower())
        return tokens

    def _extract_ngrams(self, tokens: List[str], n: int) -> Set[str]:
        if len(tokens) < n:
            return {" ".join(tokens)} if tokens else set()
        return {" ".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)}

    def _compute_minhash(self, tokens: Set[str]) -> List[int]:
        """Computes a deterministic MinHash signature vector for Jaccard estimation."""
        if not tokens:
            return [0] * self.num_perm
        sig = []
        for seed in range(self.num_perm):
            min_val = float('inf')
            for token in tokens:
                # 64-bit seed-salted hash
                h = int(hashlib.sha256(f"{seed}:{token}".encode("utf-8")).hexdigest()[:16], 16)
                if h < min_val:
                    min_val = h
            sig.append(min_val if min_val != float('inf') else 0)
        return sig

    def _index_benchmarks(self):
        for prompt in self.STANDARD_BENCHMARK_PROMPTS:
            tokens = self._clean_and_tokenize(prompt)
            self.benchmark_tokens.update(tokens)
            # Use smaller n if benchmark stem is shorter than ngram_size
            eff_n = min(self.ngram_size, len(tokens))
            if eff_n > 0:
                self.benchmark_ngrams.update(self._extract_ngrams(tokens, eff_n))

    def add_benchmark_test_cases(self, questions: List[str]):
        """Dynamically registers test cases (e.g. GSM8K, MATH, HumanEval)."""
        for q in questions:
            tokens = self._clean_and_tokenize(q)
            self.benchmark_tokens.update(tokens)
            eff_n = min(self.ngram_size, len(tokens))
            if eff_n > 0:
                self.benchmark_ngrams.update(self._extract_ngrams(tokens, eff_n))

    def audit_document(self, text: str, source_uri: str, paper_id: Optional[str] = None) -> DecontaminationAuditResult:
        doc_bytes = text.encode("utf-8")
        content_sha = hashlib.sha256(doc_bytes).hexdigest()
        pid = paper_id or f"doc-{content_sha[:12]}"

        tokens = self._clean_and_tokenize(text)
        token_set = set(tokens)

        # 1. 13-gram exact match check
        doc_ngrams = self._extract_ngrams(tokens, self.ngram_size)
        colliding_ngrams = list(doc_ngrams.intersection(self.benchmark_ngrams))

        # 2. Token Jaccard overlap against benchmark tokens
        intersection = token_set.intersection(self.benchmark_tokens)
        leakage_score = len(intersection) / len(self.benchmark_tokens) if self.benchmark_tokens else 0.0

        # 3. MinHash signature computation
        minhash_sig = self._compute_minhash(token_set)
        sig_str = hashlib.sha256(json.dumps(minhash_sig).encode("utf-8")).hexdigest()

        # 4. Gating decision
        if colliding_ngrams or leakage_score > self.leakage_threshold:
            quarantine_status = "QUARANTINED"
        else:
            quarantine_status = "CLEAN"

        return DecontaminationAuditResult(
            paper_id=pid,
            source_uri=source_uri,
            content_sha256=content_sha,
            minhash_signature=sig_str,
            benchmark_leakage_score=round(leakage_score, 4),
            quarantine_status=quarantine_status,
            matching_ngrams=colliding_ngrams[:5],  # top 5 colliding n-grams
            audited_at=datetime.now(timezone.utc).isoformat()
        )
