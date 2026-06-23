#!/bin/bash
# QUANTUM FLEX: Autonomous Goose Overseer
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/home/chambers/.local/bin

LOG_FILE="/home/chambers/quantum_flex/truth_audit.log"
GOOSE_BIN="/home/chambers/.local/bin/goose"

echo "[$(date)] >> INITIALIZING AGENTIC AUDIT SEQUENCE..." >> $LOG_FILE

# Execute headless Goose by reading the file directly, avoiding cron string expansion
cat /home/chambers/quantum_flex/audit_directive.txt | $GOOSE_BIN run >> $LOG_FILE 2>&1

echo -e "\n[$(date)] >> AUDIT CYCLE TERMINATED.\n----------------------------------------" >> $LOG_FILE
