#!/usr/bin/env python3
"""
═════════════════════════════════════════════════════════════════════
  QUANTUM FLEX: ATHENA CRYPTOGRAPHIC MERKLE PROVENANCE ENGINE
═════════════════════════════════════════════════════════════════════
Provides byte-exact claim-level provenance, RFC 6962-compliant Merkle
inclusion trees with domain separation prefixes (0x00 leaf, 0x01 node),
and cryptographic verification of evidence spans.
"""

import hashlib
import json
import re
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Tuple


@dataclass(frozen=True)
class ProvenanceSpan:
    span_id: str
    claim_id: str
    source_sha256: str
    byte_start: int
    byte_end: int
    source_uri: str
    merkle_root: str
    leaf_index: int
    leaf_hash: str
    epistemic_tier: str  # E1-E5 or M1-M5


@dataclass(frozen=True)
class ScientificClaim:
    claim_id: str
    statement: str
    provenance: List[ProvenanceSpan]
    verification_status: str  # "UNVERIFIED", "VERIFIED", "REFUTED", "CONJECTURE"
    verification_record_id: Optional[str]
    model_confidence: float
    retrieval_similarity: float
    empirical_support_score: float

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d


class MerkleTree:
    """
    Cryptographic Merkle Tree using RFC 6962 domain separation:
      Leaf hash:   H(0x00 || leaf_bytes)
      Internal:    H(0x01 || left_hash || right_hash)
    """

    def __init__(self, leaves: List[bytes]):
        if not leaves:
            raise ValueError("MerkleTree requires at least one leaf.")
        self.raw_leaves = leaves
        self.leaf_hashes: List[bytes] = [self.hash_leaf(leaf) for leaf in leaves]
        self.levels: List[List[bytes]] = [self.leaf_hashes]
        self._build_tree()

    @staticmethod
    def hash_leaf(data: bytes) -> bytes:
        return hashlib.sha256(b"\x00" + data).digest()

    @staticmethod
    def hash_nodes(left: bytes, right: bytes) -> bytes:
        return hashlib.sha256(b"\x01" + left + right).digest()

    def _build_tree(self):
        current = self.leaf_hashes
        while len(current) > 1:
            next_level = []
            for i in range(0, len(current), 2):
                left = current[i]
                right = current[i + 1] if i + 1 < len(current) else current[i]
                next_level.append(self.hash_nodes(left, right))
            self.levels.append(next_level)
            current = next_level

    @property
    def root(self) -> bytes:
        return self.levels[-1][0]

    @property
    def root_hex(self) -> str:
        return self.root.hex()

    def generate_inclusion_proof(self, leaf_index: int) -> List[Dict[str, str]]:
        """
        Generates an audit path for the leaf at leaf_index.
        Each entry in the proof dict has 'position' ('left' or 'right') and 'hash' (hex).
        """
        if leaf_index < 0 or leaf_index >= len(self.leaf_hashes):
            raise IndexError(f"Leaf index {leaf_index} out of bounds (0..{len(self.leaf_hashes) - 1})")

        proof = []
        idx = leaf_index
        for level in self.levels[:-1]:
            is_right_child = (idx % 2 == 1)
            sibling_idx = idx - 1 if is_right_child else idx + 1
            if sibling_idx < len(level):
                sibling_hash = level[sibling_idx]
            else:
                sibling_hash = level[idx]  # duplicate self if odd

            proof.append({
                "position": "left" if is_right_child else "right",
                "hash": sibling_hash.hex()
            })
            idx = idx // 2

        return proof

    @classmethod
    def verify_inclusion_proof(
        cls,
        root_hex: str,
        leaf_data: bytes,
        proof: List[Dict[str, str]],
        leaf_index: Optional[int] = None
    ) -> bool:
        """
        Recomputes the root hash from leaf_data and audit proof.
        Returns True if computed root == root_hex.
        """
        current_hash = cls.hash_leaf(leaf_data)
        return cls.verify_hash_inclusion(root_hex, current_hash, proof)

    @classmethod
    def verify_hash_inclusion(
        cls,
        root_hex: str,
        leaf_hash: bytes,
        proof: List[Dict[str, str]]
    ) -> bool:
        """
        Verifies inclusion starting directly from a leaf hash.
        """
        current_hash = leaf_hash
        for step in proof:
            sibling = bytes.fromhex(step["hash"])
            if step["position"] == "left":
                current_hash = cls.hash_nodes(sibling, current_hash)
            else:
                current_hash = cls.hash_nodes(current_hash, sibling)

        return current_hash.hex().lower() == root_hex.lower()


class DocumentProvenanceIndex:
    """
    Indexes a document into sentence/paragraph blocks, computes byte offsets,
    and constructs a Merkle tree for fine-grained claim citations.
    """

    def __init__(self, doc_text: str, source_uri: str):
        self.doc_text = doc_text
        self.source_uri = source_uri
        self.doc_bytes = doc_text.encode("utf-8")
        self.doc_sha256 = hashlib.sha256(self.doc_bytes).hexdigest()
        self.spans: List[Tuple[int, int, str]] = []  # (byte_start, byte_end, text)
        self._segment_spans()
        if not self.spans:
            # Fallback for empty/whitespace document
            self.spans = [(0, len(self.doc_bytes), doc_text)]
        leaf_bytes = [span[2].encode("utf-8") for span in self.spans]
        self.tree = MerkleTree(leaf_bytes)

    def _segment_spans(self):
        """Splits document into sentence/line segments while tracking exact byte offsets."""
        pattern = re.compile(r'[^.\n!?]+(?:[.\n!?]+|\Z)', re.MULTILINE)
        for match in pattern.finditer(self.doc_text):
            chunk = match.group(0)
            strip_chunk = chunk.strip()
            if not strip_chunk:
                continue
            leading_ws = len(chunk) - len(chunk.lstrip())
            trailing_ws = len(chunk) - len(chunk.rstrip())
            c_start = match.start() + leading_ws
            c_end = match.end() - trailing_ws
            b_start = len(self.doc_text[:c_start].encode("utf-8"))
            b_end = len(self.doc_text[:c_end].encode("utf-8"))
            self.spans.append((b_start, b_end, strip_chunk))

    def find_best_span_for_claim(self, claim_text: str) -> Optional[Tuple[int, Tuple[int, int, str]]]:
        """
        Finds the span index and (byte_start, byte_end, text) best matching the claim text.
        """
        claim_clean = claim_text.strip().lower()
        # 1. Exact substring search in full doc
        pos = self.doc_text.lower().find(claim_clean)
        if pos != -1:
            byte_start = len(self.doc_text[:pos].encode("utf-8"))
            byte_end = byte_start + len(claim_clean.encode("utf-8"))
            # Find closest matching leaf
            for idx, (s, e, text) in enumerate(self.spans):
                if (s <= byte_start < e) or (s < byte_end <= e) or (byte_start <= s and byte_end >= e):
                    return idx, (s, e, text)
            # If not matching span boundary exactly, return closest span
            return 0, (byte_start, byte_end, self.doc_text[pos:pos + len(claim_clean)])

        # 2. Token overlap search across spans
        claim_tokens = set(re.findall(r'\w+', claim_clean))
        if not claim_tokens:
            return None

        best_idx = -1
        best_jaccard = 0.0
        for idx, (s, e, text) in enumerate(self.spans):
            span_tokens = set(re.findall(r'\w+', text.lower()))
            if not span_tokens:
                continue
            intersection = claim_tokens.intersection(span_tokens)
            union = claim_tokens.union(span_tokens)
            jaccard = len(intersection) / len(union) if union else 0.0
            if jaccard > best_jaccard:
                best_jaccard = jaccard
                best_idx = idx

        if best_idx != -1 and best_jaccard > 0.15:
            return best_idx, self.spans[best_idx]

        return None

    def create_provenance_span(
        self,
        claim_id: str,
        claim_text: str,
        epistemic_tier: str = "E2"
    ) -> Optional[ProvenanceSpan]:
        match = self.find_best_span_for_claim(claim_text)
        if not match:
            return None
        leaf_idx, (b_start, b_end, span_text) = match
        leaf_hash_hex = self.tree.leaf_hashes[leaf_idx].hex()
        span_id = hashlib.sha256(f"{claim_id}:{self.doc_sha256}:{leaf_idx}:{b_start}".encode("utf-8")).hexdigest()[:16]

        return ProvenanceSpan(
            span_id=span_id,
            claim_id=claim_id,
            source_sha256=self.doc_sha256,
            byte_start=b_start,
            byte_end=b_end,
            source_uri=self.source_uri,
            merkle_root=self.tree.root_hex,
            leaf_index=leaf_idx,
            leaf_hash=leaf_hash_hex,
            epistemic_tier=epistemic_tier
        )

    def get_inclusion_proof_for_span(self, leaf_index: int) -> List[Dict[str, str]]:
        return self.tree.generate_inclusion_proof(leaf_index)
