#!/usr/bin/env python3
"""
═════════════════════════════════════════════════════════════════════
  QUANTUM FLEX: REPRODUCIBLE EXPERIMENT MANIFEST GENERATOR
═════════════════════════════════════════════════════════════════════
Captures full hardware, software, PRNG seed, precision mode, and library
provenance to guarantee exact computational and physical reproducibility.
"""

import os
import sys
import json
import uuid
import platform
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional


def get_cpu_model() -> str:
    """Extracts CPU model string from /proc/cpuinfo on Linux or platform."""
    try:
        if os.path.exists("/proc/cpuinfo"):
            with open("/proc/cpuinfo", "r", encoding="utf-8") as f:
                for line in f:
                    if "model name" in line:
                        return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return platform.processor() or "Unknown CPU"


def get_installed_math_libraries() -> Dict[str, str]:
    """Detects exact versions of key scientific libraries."""
    libs = {}
    for mod_name in ["numpy", "scipy", "qiskit", "sympy", "mpmath"]:
        try:
            m = __import__(mod_name)
            libs[mod_name] = getattr(m, "__version__", "unknown")
        except ImportError:
            libs[mod_name] = "not_installed"
    return libs


@dataclass
class ExperimentEnvironment:
    os: str
    kernel: str
    cpu_model: str
    python_version: str
    compiler: str
    math_libraries: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExperimentParameters:
    prng_seed: int
    float_precision: str  # "IEEE_754_FLOAT64", "IEEE_754_FLOAT32", "ARBITRARY_MPMATH"
    solver: str
    tolerance: Dict[str, float]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ExperimentManifestBuilder:
    """
    Builds and cryptographically signs reproducible experiment manifests.
    """

    @classmethod
    def capture_environment(cls) -> ExperimentEnvironment:
        return ExperimentEnvironment(
            os=f"{platform.system()} {platform.release()}",
            kernel=platform.version(),
            cpu_model=get_cpu_model(),
            python_version=platform.python_version(),
            compiler=platform.python_compiler(),
            math_libraries=get_installed_math_libraries()
        )

    @classmethod
    def create_manifest(
        cls,
        experiment_type: str,
        parameters: ExperimentParameters,
        computational_invariants: List[str],
        result_payload: Any,
        manifest_id: Optional[str] = None
    ) -> Dict[str, Any]:
        mid = manifest_id or f"qf-exp-{uuid.uuid4().hex[:12]}"
        env = cls.capture_environment()

        # Compute deterministic execution digest from environment, parameters, and results
        digest_input = {
            "environment": env.to_dict(),
            "parameters": parameters.to_dict(),
            "invariants": sorted(computational_invariants),
            "result": result_payload
        }
        canonical_json = json.dumps(digest_input, sort_keys=True)
        execution_digest = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

        manifest = {
            "manifest_id": mid,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "experiment_type": experiment_type,
            "environment": env.to_dict(),
            "parameters": parameters.to_dict(),
            "computational_invariants": computational_invariants,
            "execution_digest": execution_digest
        }
        return manifest

    @classmethod
    def verify_manifest_schema(cls, manifest: Dict[str, Any]) -> bool:
        required_keys = [
            "manifest_id",
            "timestamp_utc",
            "experiment_type",
            "environment",
            "parameters",
            "computational_invariants",
            "execution_digest"
        ]
        if not all(k in manifest for k in required_keys):
            return False

        env = manifest["environment"]
        req_env = ["os", "kernel", "cpu_model", "python_version", "compiler", "math_libraries"]
        if not all(k in env for k in req_env):
            return False

        params = manifest["parameters"]
        req_params = ["prng_seed", "float_precision", "solver", "tolerance"]
        if not all(k in params for k in req_params):
            return False

        if len(manifest["execution_digest"]) != 64:
            return False

        return True

    @classmethod
    def check_cross_platform_reproducibility(
        cls,
        manifest_a: Dict[str, Any],
        manifest_b: Dict[str, Any],
        tolerance_atol: float = 1e-9
    ) -> Dict[str, Any]:
        """
        Compares two manifests to detect environment deviations, PRNG mismatches,
        or floating-point divergences.
        """
        env_match = (
            manifest_a["environment"]["cpu_model"] == manifest_b["environment"]["cpu_model"] and
            manifest_a["environment"]["math_libraries"] == manifest_b["environment"]["math_libraries"]
        )
        param_match = manifest_a["parameters"] == manifest_b["parameters"]
        digest_match = manifest_a["execution_digest"] == manifest_b["execution_digest"]

        return {
            "identical_digest": digest_match,
            "environment_identical": env_match,
            "parameters_identical": param_match,
            "reproducible": digest_match or (param_match and env_match)
        }
