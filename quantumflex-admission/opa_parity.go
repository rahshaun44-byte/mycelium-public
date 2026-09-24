package main

import (
	"archive/tar"
	"bytes"
	"compress/gzip"
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	_ "github.com/open-policy-agent/opa/features/wasm"
	"github.com/open-policy-agent/opa/rego"
	"github.com/open-policy-agent/opa/storage/inmem"
)

// EvaluateNative evaluates the input and data against the native Rego policy.
func EvaluateNative(ctx context.Context, regoPath string, input *OPAInput, data *OPAData) (bool, error) {
	b, err := os.ReadFile(regoPath)
	if err != nil {
		return false, fmt.Errorf("failed to read rego: %w", err)
	}

	dataMap := make(map[string]interface{})
	dataBytes, err := json.Marshal(data)
	if err != nil {
		return false, fmt.Errorf("failed to marshal data: %w", err)
	}
	if err := json.Unmarshal(dataBytes, &dataMap); err != nil {
		return false, fmt.Errorf("failed to unmarshal data map: %w", err)
	}

	inputMap := make(map[string]interface{})
	inputBytes, err := json.Marshal(input)
	if err != nil {
		return false, fmt.Errorf("failed to marshal input: %w", err)
	}
	if err := json.Unmarshal(inputBytes, &inputMap); err != nil {
		return false, fmt.Errorf("failed to unmarshal input map: %w", err)
	}

	r := rego.New(
		rego.Query("data.quantumflex.bootgate.allow"),
		rego.Module(filepath.Base(regoPath), string(b)),
		rego.Store(inmem.NewFromObject(dataMap)),
	)

	query, err := r.PrepareForEval(ctx)
	if err != nil {
		return false, fmt.Errorf("failed to prepare rego: %w", err)
	}

	rs, err := query.Eval(ctx, rego.EvalInput(inputMap))
	if err != nil {
		return false, fmt.Errorf("eval failed: %w", err)
	}

	if len(rs) > 0 && len(rs[0].Expressions) > 0 {
		if allow, ok := rs[0].Expressions[0].Value.(bool); ok {
			return allow, nil
		}
	}

	return false, nil
}

// BuildWasmBundle creates an OPA-compliant bundle.tar.gz from wasm bytes and data map.
func BuildWasmBundle(wasmBytes []byte, dataMap map[string]interface{}) ([]byte, error) {
	manifest := map[string]interface{}{
		"roots": []string{"quantumflex", "anchor", "environment", "ledger"},
		"wasm": []map[string]interface{}{
			{
				"entrypoint": "quantumflex/bootgate/allow",
				"module":     "/policy.wasm",
			},
		},
	}
	manifestBytes, err := json.Marshal(manifest)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal manifest: %w", err)
	}

	dataJson, err := json.Marshal(dataMap)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal data.json: %w", err)
	}

	buf := &bytes.Buffer{}
	gw := gzip.NewWriter(buf)
	tw := tar.NewWriter(gw)

	if err := tw.WriteHeader(&tar.Header{Name: "/.manifest", Size: int64(len(manifestBytes))}); err != nil {
		return nil, fmt.Errorf("failed to write manifest header: %w", err)
	}
	if _, err := tw.Write(manifestBytes); err != nil {
		return nil, fmt.Errorf("failed to write manifest: %w", err)
	}

	if err := tw.WriteHeader(&tar.Header{Name: "/policy.wasm", Size: int64(len(wasmBytes))}); err != nil {
		return nil, fmt.Errorf("failed to write wasm header: %w", err)
	}
	if _, err := tw.Write(wasmBytes); err != nil {
		return nil, fmt.Errorf("failed to write wasm: %w", err)
	}

	if err := tw.WriteHeader(&tar.Header{Name: "/data.json", Size: int64(len(dataJson))}); err != nil {
		return nil, fmt.Errorf("failed to write data.json header: %w", err)
	}
	if _, err := tw.Write(dataJson); err != nil {
		return nil, fmt.Errorf("failed to write data.json: %w", err)
	}

	if err := tw.Close(); err != nil {
		return nil, fmt.Errorf("failed to close tar writer: %w", err)
	}
	if err := gw.Close(); err != nil {
		return nil, fmt.Errorf("failed to close gzip writer: %w", err)
	}

	return buf.Bytes(), nil
}

// EvaluateWasm evaluates the input and data against the WASM-compiled policy.
func EvaluateWasm(ctx context.Context, wasmPath string, input *OPAInput, data *OPAData) (bool, error) {
	dataMap := make(map[string]interface{})
	dataBytes, err := json.Marshal(data)
	if err != nil {
		return false, fmt.Errorf("failed to marshal data: %w", err)
	}
	if err := json.Unmarshal(dataBytes, &dataMap); err != nil {
		return false, fmt.Errorf("failed to unmarshal data map: %w", err)
	}

	inputMap := make(map[string]interface{})
	inputBytes, err := json.Marshal(input)
	if err != nil {
		return false, fmt.Errorf("failed to marshal input: %w", err)
	}
	if err := json.Unmarshal(inputBytes, &inputMap); err != nil {
		return false, fmt.Errorf("failed to unmarshal input map: %w", err)
	}

	wasmBytes, err := os.ReadFile(wasmPath)
	if err != nil {
		return false, fmt.Errorf("failed to read wasm file: %w", err)
	}

	bundleBytes, err := BuildWasmBundle(wasmBytes, dataMap)
	if err != nil {
		return false, err
	}

	tmpFile, err := os.CreateTemp("", "bundle-*.tar.gz")
	if err != nil {
		return false, fmt.Errorf("failed to create temp bundle file: %w", err)
	}
	defer os.Remove(tmpFile.Name())

	if _, err := tmpFile.Write(bundleBytes); err != nil {
		tmpFile.Close()
		return false, fmt.Errorf("failed to write bundle bytes: %w", err)
	}
	if err := tmpFile.Close(); err != nil {
		return false, fmt.Errorf("failed to close temp bundle file: %w", err)
	}

	r := rego.New(
		rego.Query("data.quantumflex.bootgate.allow"),
		rego.LoadBundle(tmpFile.Name()),
	)

	query, err := r.PrepareForEval(ctx)
	if err != nil {
		return false, fmt.Errorf("failed to prepare rego wasm: %w", err)
	}

	rs, err := query.Eval(ctx, rego.EvalInput(inputMap))
	if err != nil {
		return false, fmt.Errorf("eval wasm failed: %w", err)
	}

	if len(rs) > 0 && len(rs[0].Expressions) > 0 {
		if allow, ok := rs[0].Expressions[0].Value.(bool); ok {
			return allow, nil
		}
	}

	return false, nil
}
