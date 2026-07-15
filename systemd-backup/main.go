package main

import (
	"fmt"
	"log"
	"net/http"
	"time"
)

// A.M.A.R.A. Integration Stub
type AMARACommand struct {
	Task     string
	Priority int
}

func processAMARA(cmd AMARACommand) {
	log.Printf("A.M.A.R.A. Processing: %s (Pri: %d) via Ghost Node", cmd.Task, cmd.Priority)
	// TODO: Add telemetry push, encryption, task delegation
}

func healthHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	fmt.Fprintf(w, `{"status":"alive","node":"ghost-node-agent","timestamp":"%s"}`, time.Now().Format(time.RFC3339))
}

func main() {
	log.Println("Ghost Node Agent starting - Telemetry root active")
	log.Println("SECURITY: Binding exclusively to 127.0.0.1:8080")

	// Health endpoint — localhost only
	http.HandleFunc("/health", healthHandler)
	go func() {
		// CRITICAL: Bind to localhost ONLY — never 0.0.0.0
		if err := http.ListenAndServe("127.0.0.1:8080", nil); err != nil {
			log.Fatalf("HTTP server failed: %v", err)
		}
	}()

	// Heartbeat + A.M.A.R.A. telemetry loop
	for {
		fmt.Println("Heartbeat:", time.Now())
		processAMARA(AMARACommand{Task: "Telemetry Sync", Priority: 1})
		time.Sleep(60 * time.Second)
	}
}
