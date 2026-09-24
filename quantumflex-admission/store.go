package main

import (
	"database/sql"
	"fmt"
	"net/url"
	"strings"

	_ "github.com/mattn/go-sqlite3"
)

type Store struct {
	db *sql.DB
}

type Anchor struct {
	Sequence    uint64 `json:"sequence"`
	StateDigest string `json:"state_digest"`
}

func sanitizeDSN(dsn string) string {
	parts := strings.SplitN(dsn, "?", 2)
	base := parts[0]
	var query url.Values
	if len(parts) == 2 {
		var err error
		query, err = url.ParseQuery(parts[1])
		if err != nil {
			query = url.Values{}
		}
	} else {
		query = url.Values{}
	}
	query.Set("_txlock", "immediate")
	return base + "?" + query.Encode()
}

func NewStore(dsn string) (*Store, error) {
	return NewStoreWithGenesis(dsn, 1, "sha3:STATE_K1")
}

func NewStoreWithGenesis(dsn string, initialSeq uint64, initialDigest string) (*Store, error) {
	sanitized := sanitizeDSN(dsn)
	db, err := sql.Open("sqlite3", sanitized)
	if err != nil {
		return nil, err
	}

	// Create tables if they don't exist with full bounds checking
	_, err = db.Exec(`
		CREATE TABLE IF NOT EXISTS anchor (
			id INTEGER PRIMARY KEY CHECK (id = 1),
			sequence INTEGER NOT NULL CHECK (sequence >= 1 AND sequence <= 9007199254740991),
			state_digest TEXT NOT NULL
		);
		CREATE TABLE IF NOT EXISTS ledger (
			decision_id TEXT PRIMARY KEY,
			sequence INTEGER UNIQUE NOT NULL CHECK(sequence >= 1 AND sequence <= 9007199254740991),
			result TEXT NOT NULL CHECK(result IN ('ALLOW', 'DENY')),
			timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
		);
	`)
	if err != nil {
		db.Close()
		return nil, fmt.Errorf("failed to initialize schema: %w", err)
	}

	if err := migrateSchema(db); err != nil {
		db.Close()
		return nil, fmt.Errorf("schema migration failed: %w", err)
	}

	_, err = db.Exec(`INSERT OR IGNORE INTO anchor (id, sequence, state_digest) VALUES (1, ?, ?);`, initialSeq, initialDigest)
	if err != nil {
		db.Close()
		return nil, fmt.Errorf("failed to initialize genesis anchor: %w", err)
	}

	return &Store{db: db}, nil
}

func migrateSchema(db *sql.DB) error {
	var sqlDef string
	err := db.QueryRow("SELECT sql FROM sqlite_master WHERE type='table' AND name='ledger'").Scan(&sqlDef)
	if err == nil {
		if !strings.Contains(sqlDef, "ALLOW") || !strings.Contains(sqlDef, "9007199254740991") {
			tx, err := db.Begin()
			if err != nil {
				return err
			}
			defer tx.Rollback()

			_, err = tx.Exec(`
				CREATE TABLE IF NOT EXISTS ledger_new (
					decision_id TEXT PRIMARY KEY,
					sequence INTEGER UNIQUE NOT NULL CHECK(sequence >= 1 AND sequence <= 9007199254740991),
					result TEXT NOT NULL CHECK(result IN ('ALLOW', 'DENY')),
					timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
				);
				INSERT OR IGNORE INTO ledger_new (decision_id, sequence, result, timestamp)
					SELECT decision_id, sequence, result, timestamp FROM ledger;
				DROP TABLE ledger;
				ALTER TABLE ledger_new RENAME TO ledger;
			`)
			if err != nil {
				return fmt.Errorf("migration failed for ledger: %w", err)
			}
			if err := tx.Commit(); err != nil {
				return err
			}
		}
	}

	var anchorDef string
	err = db.QueryRow("SELECT sql FROM sqlite_master WHERE type='table' AND name='anchor'").Scan(&anchorDef)
	if err == nil {
		if !strings.Contains(anchorDef, "9007199254740991") {
			tx, err := db.Begin()
			if err != nil {
				return err
			}
			defer tx.Rollback()

			_, err = tx.Exec(`
				CREATE TABLE IF NOT EXISTS anchor_new (
					id INTEGER PRIMARY KEY CHECK (id = 1),
					sequence INTEGER NOT NULL CHECK (sequence >= 1 AND sequence <= 9007199254740991),
					state_digest TEXT NOT NULL
				);
				INSERT OR IGNORE INTO anchor_new (id, sequence, state_digest)
					SELECT id, sequence, state_digest FROM anchor;
				DROP TABLE anchor;
				ALTER TABLE anchor_new RENAME TO anchor;
			`)
			if err != nil {
				return fmt.Errorf("migration failed for anchor: %w", err)
			}
			if err := tx.Commit(); err != nil {
				return err
			}
		}
	}
	return nil
}

func (s *Store) Close() error {
	return s.db.Close()
}

func (s *Store) GetAnchor() (Anchor, error) {
	var a Anchor
	err := s.db.QueryRow("SELECT sequence, state_digest FROM anchor WHERE id = 1").Scan(&a.Sequence, &a.StateDigest)
	return a, err
}

func (s *Store) GetConsumedDecisions() ([]string, error) {
	rows, err := s.db.Query("SELECT decision_id FROM ledger")
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var decisions []string
	for rows.Next() {
		var id string
		if err := rows.Scan(&id); err != nil {
			return nil, err
		}
		decisions = append(decisions, id)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	return decisions, nil
}

// CommitTransition implements an atomic state transition in a single transaction.
func (s *Store) CommitTransition(decisionID string, newSequence uint64, newStateDigest string, result string, expectedOldSequence uint64, expectedPreviousDigest string) error {
	if newSequence > MaxSequence {
		return fmt.Errorf("monotonicity violation: sequence %d exceeds MaxSequence limit (%d)", newSequence, MaxSequence)
	}

	if result != "ALLOW" {
		return fmt.Errorf("transaction rejected: only ALLOW decisions can mutate the authoritative anchor")
	}

	tx, err := s.db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()

	var currentSeq uint64
	var currentDigest string
	err = tx.QueryRow("SELECT sequence, state_digest FROM anchor WHERE id = 1").Scan(&currentSeq, &currentDigest)
	if err != nil {
		return fmt.Errorf("failed to read anchor during transaction: %w", err)
	}

	if currentSeq != expectedOldSequence {
		return fmt.Errorf("concurrency violation: expected sequence %d, got %d", expectedOldSequence, currentSeq)
	}

	if expectedPreviousDigest != "" && currentDigest != expectedPreviousDigest {
		return fmt.Errorf("continuity violation: expected previous digest %s, got %s", expectedPreviousDigest, currentDigest)
	}

	if newSequence != currentSeq+1 {
		return fmt.Errorf("monotonicity violation: new sequence %d does not sequentially follow %d", newSequence, currentSeq)
	}

	// Insert decision into ledger (fails if decision_id or sequence already exists due to PRIMARY KEY / UNIQUE)
	_, err = tx.Exec("INSERT INTO ledger (decision_id, sequence, result) VALUES (?, ?, ?)", decisionID, newSequence, result)
	if err != nil {
		return fmt.Errorf("failed to write decision ledger: %w", err)
	}

	// Update anchor
	_, err = tx.Exec("UPDATE anchor SET sequence = ?, state_digest = ? WHERE id = 1", newSequence, newStateDigest)
	if err != nil {
		return fmt.Errorf("failed to update anchor: %w", err)
	}

	return tx.Commit()
}
