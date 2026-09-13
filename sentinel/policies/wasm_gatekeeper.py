#!/usr/bin/env python3
"""
=====================================================================
  QUANTUM FLEX // ZERO-FRICTION GATEKEEPER (Wasm In-Process Engine)
=====================================================================
Embedded WebAssembly evaluation engine for Open Policy Agent (OPA)
compiled modules. Eliminates network serialization and HTTP loopback
latency (~1.2 ms down to sub-millisecond in-process evaluation).

Supports:
  - membrane_health.wasm (CycloneDX CBOM compliance & threat flags)
  - reserve_invariant.wasm (R >= O Universal Solvency Gate)
"""

import os
import sys
import json
import time
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import wasmtime
except ImportError:
    wasmtime = None

POLICY_DIR = Path(__file__).resolve().parent
MEMBRANE_WASM = POLICY_DIR / "membrane_health.wasm"
RESERVE_WASM = POLICY_DIR / "reserve_invariant.wasm"


class OPAWasmEngine:
    def __init__(self, wasm_path: Union[str, Path]):
        if wasmtime is None:
            raise RuntimeError("wasmtime module is not installed in the active environment.")

        self.wasm_path = Path(wasm_path)
        if not self.wasm_path.is_file():
            raise FileNotFoundError(f"OPA Wasm module not found: {self.wasm_path}")

        self.engine = wasmtime.Engine()
        self.store = wasmtime.Store(self.engine)
        self.memory = wasmtime.Memory(self.store, wasmtime.MemoryType(wasmtime.Limits(2, None)))

        self.linker = wasmtime.Linker(self.engine)
        self.linker.define(self.store, "env", "memory", self.memory)
        self.linker.define_func(
            "env", "opa_abort",
            wasmtime.FuncType([wasmtime.ValType.i32()], []),
            self._opa_abort
        )
        self.linker.define_func(
            "env", "opa_builtin0",
            wasmtime.FuncType([wasmtime.ValType.i32()]*2, [wasmtime.ValType.i32()]),
            lambda b, ctx: self._dispatch_builtin(b, ctx)
        )
        self.linker.define_func(
            "env", "opa_builtin1",
            wasmtime.FuncType([wasmtime.ValType.i32()]*3, [wasmtime.ValType.i32()]),
            lambda b, ctx, a1: self._dispatch_builtin(b, ctx, a1)
        )
        self.linker.define_func(
            "env", "opa_builtin2",
            wasmtime.FuncType([wasmtime.ValType.i32()]*4, [wasmtime.ValType.i32()]),
            lambda b, ctx, a1, a2: self._dispatch_builtin(b, ctx, a1, a2)
        )
        self.linker.define_func(
            "env", "opa_builtin3",
            wasmtime.FuncType([wasmtime.ValType.i32()]*5, [wasmtime.ValType.i32()]),
            lambda b, ctx, a1, a2, a3: self._dispatch_builtin(b, ctx, a1, a2, a3)
        )
        self.linker.define_func(
            "env", "opa_builtin4",
            wasmtime.FuncType([wasmtime.ValType.i32()]*6, [wasmtime.ValType.i32()]),
            lambda b, ctx, a1, a2, a3, a4: self._dispatch_builtin(b, ctx, a1, a2, a3, a4)
        )

        self.module = wasmtime.Module.from_file(self.engine, str(self.wasm_path))
        self.instance = self.linker.instantiate(self.store, self.module)
        self.exports = self.instance.exports(self.store)

        # Cache builtins and entrypoints mapping
        self.builtins = self._read_json(self.exports["builtins"](self.store))
        self.entrypoints = self._read_json(self.exports["entrypoints"](self.store))

        # Cache base heap pointer to recycle between runs
        self.base_heap_ptr = self.exports["opa_heap_ptr_get"](self.store)

    def _opa_abort(self, addr: int) -> None:
        raw = self.memory.data_ptr(self.store)
        chars = []
        idx = addr
        while raw[idx] != 0:
            chars.append(chr(raw[idx]))
            idx += 1
        msg = "".join(chars)
        raise RuntimeError(f"OPA Wasm abort: {msg}")

    def _read_json(self, val_ref: int) -> Any:
        dump_addr = self.exports["opa_json_dump"](self.store, val_ref)
        mem = self.memory.data_ptr(self.store)
        chars = []
        idx = dump_addr
        while mem[idx] != 0:
            chars.append(chr(mem[idx]))
            idx += 1
        return json.loads("".join(chars))

    def _write_json(self, val: Any) -> int:
        encoded = json.dumps(val).encode("utf-8")
        addr = self.exports["opa_malloc"](self.store, len(encoded))
        mem = self.memory.data_ptr(self.store)
        for i, b in enumerate(encoded):
            mem[addr + i] = b
        return self.exports["opa_json_parse"](self.store, addr, len(encoded))

    def _dispatch_builtin(self, builtin_id: int, ctx: int, *args: int) -> int:
        # Builtin: sprintf (ID 4)
        if builtin_id == 4 and len(args) >= 2:
            fmt_str = self._read_json(args[0])
            fmt_args = self._read_json(args[1])
            res = fmt_str
            for a in fmt_args:
                val_str = str(a) if not isinstance(a, (dict, list)) else json.dumps(a)
                res = re.sub(r"%(v|s|d)", val_str, res, count=1)
            return self._write_json(res)

        # Builtin: time.now_ns (ID 10)
        if builtin_id == 10:
            return self._write_json(time.time_ns())

        return 0

    def evaluate(self, input_data: Any, data: Optional[Dict[str, Any]] = None, entrypoint_id: int = 0) -> Any:
        heap_snapshot = self.exports["opa_heap_ptr_get"](self.store)
        try:
            input_ref = self._write_json(input_data)
            data_ref = self._write_json(data or {})

            ctx = self.exports["opa_eval_ctx_new"](self.store)
            self.exports["opa_eval_ctx_set_entrypoint"](self.store, ctx, entrypoint_id)
            self.exports["opa_eval_ctx_set_data"](self.store, ctx, data_ref)
            self.exports["opa_eval_ctx_set_input"](self.store, ctx, input_ref)

            self.exports["eval"](self.store, ctx)
            result_ref = self.exports["opa_eval_ctx_get_result"](self.store, ctx)
            results = self._read_json(result_ref)
            if isinstance(results, list) and len(results) > 0 and "result" in results[0]:
                return results[0]["result"]
            return results
        finally:
            # Landauer memory reclamation: restore heap pointer to prevent memory growth
            self.exports["opa_heap_ptr_set"](self.store, heap_snapshot)


class MembraneHealthWasmGatekeeper:
    def __init__(self, wasm_path: Optional[Path] = None):
        target_path = wasm_path or MEMBRANE_WASM
        self.engine = OPAWasmEngine(target_path)
        self.ep_verdict = self.engine.entrypoints.get("membrane/health/verdict", 0)
        self.ep_fallback_map = self.engine.entrypoints.get("membrane/health/fallback_map", 1)
        self.ep_recovery_map = self.engine.entrypoints.get("membrane/health/recovery_map", 2)

    def evaluate_verdict(self, cbom: Dict[str, Any], threat_flags: Optional[Dict[str, bool]] = None) -> Dict[str, Any]:
        data = {"threat_flags": threat_flags or {}}
        return self.engine.evaluate(input_data=cbom, data=data, entrypoint_id=self.ep_verdict)

    def get_fallback_map(self) -> Dict[str, str]:
        return self.engine.evaluate(input_data={}, data={}, entrypoint_id=self.ep_fallback_map)

    def get_recovery_map(self) -> Dict[str, Any]:
        return self.engine.evaluate(input_data={}, data={}, entrypoint_id=self.ep_recovery_map)


class ReserveInvariantWasmGatekeeper:
    def __init__(self, wasm_path: Optional[Path] = None):
        target_path = wasm_path or RESERVE_WASM
        self.engine = OPAWasmEngine(target_path)
        self.ep_invariant = self.engine.entrypoints.get("quantumflex/invariant", 0)

    def evaluate_invariant(self, payload: Dict[str, Any]) -> Tuple[bool, str, str]:
        res = self.engine.evaluate(input_data=payload, data={}, entrypoint_id=self.ep_invariant)
        if isinstance(res, dict):
            allow = res.get("allow", False)
            verdict = res.get("verdict", "DENY")
            reason = res.get("reason", "Invariant evaluation failed")
            return allow, verdict, reason
        return False, "DENY", "Invalid evaluation payload"


_MEMBRANE_GATEKEEPER: Optional[MembraneHealthWasmGatekeeper] = None
_RESERVE_GATEKEEPER: Optional[ReserveInvariantWasmGatekeeper] = None


def get_membrane_wasm_gatekeeper() -> Optional[MembraneHealthWasmGatekeeper]:
    global _MEMBRANE_GATEKEEPER
    if _MEMBRANE_GATEKEEPER is None and MEMBRANE_WASM.is_file() and wasmtime is not None:
        try:
            _MEMBRANE_GATEKEEPER = MembraneHealthWasmGatekeeper(MEMBRANE_WASM)
        except Exception:
            _MEMBRANE_GATEKEEPER = None
    return _MEMBRANE_GATEKEEPER


def get_reserve_wasm_gatekeeper() -> Optional[ReserveInvariantWasmGatekeeper]:
    global _RESERVE_GATEKEEPER
    if _RESERVE_GATEKEEPER is None and RESERVE_WASM.is_file() and wasmtime is not None:
        try:
            _RESERVE_GATEKEEPER = ReserveInvariantWasmGatekeeper(RESERVE_WASM)
        except Exception:
            _RESERVE_GATEKEEPER = None
    return _RESERVE_GATEKEEPER
