// Package store owns SQLite access. All values use SQL parameters.
package store

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"

	"example.com/refactoring/userapi/internal/model"
	_ "modernc.org/sqlite"
)

type SQLite struct{ db *sql.DB }

func Open(path string) (*SQLite, error) {
	if err := os.MkdirAll(filepath.Dir(path), 0700); err != nil {
		return nil, fmt.Errorf("create data directory: %w", err)
	}
	db, err := sql.Open("sqlite", path)
	if err != nil {
		return nil, fmt.Errorf("open database: %w", err)
	}
	// Serialize writes on this process and apply PRAGMAs to its sole connection.
	db.SetMaxOpenConns(1)
	db.SetMaxIdleConns(1)
	for _, statement := range []string{
		"PRAGMA busy_timeout=5000",
		"PRAGMA journal_mode=WAL",
		`CREATE TABLE IF NOT EXISTS users (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		name TEXT NOT NULL, tags TEXT NOT NULL, password_hash TEXT)`,
	} {
		if _, err = db.Exec(statement); err != nil {
			db.Close()
			return nil, fmt.Errorf("initialize database: %w", err)
		}
	}
	return &SQLite{db: db}, nil
}

func (s *SQLite) Close() error                   { return s.db.Close() }
func (s *SQLite) Ping(ctx context.Context) error { return s.db.PingContext(ctx) }

func (s *SQLite) Add(ctx context.Context, name string, tags []string) (model.User, error) {
	encoded, err := json.Marshal(tags)
	if err != nil {
		return model.User{}, err
	}
	result, err := s.db.ExecContext(ctx, "INSERT INTO users(name,tags) VALUES (?,?)", name, string(encoded))
	if err != nil {
		return model.User{}, fmt.Errorf("insert user: %w", err)
	}
	id, err := result.LastInsertId()
	return model.User{ID: id, Name: name, Tags: append([]string{}, tags...)}, err
}

func readUser(row *sql.Row) (model.User, error) {
	var user model.User
	var tags string
	if err := row.Scan(&user.ID, &user.Name, &tags); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return user, model.ErrNotFound
		}
		return user, err
	}
	if err := json.Unmarshal([]byte(tags), &user.Tags); err != nil {
		return model.User{}, fmt.Errorf("decode stored tags: %w", err)
	}
	return user, nil
}

func (s *SQLite) Get(ctx context.Context, id int64) (model.User, error) {
	return readUser(s.db.QueryRowContext(ctx, "SELECT id,name,tags FROM users WHERE id=?", id))
}

func (s *SQLite) ByName(ctx context.Context, name string) (model.User, error) {
	return readUser(s.db.QueryRowContext(ctx, "SELECT id,name,tags FROM users WHERE name=? ORDER BY id LIMIT 1", name))
}

func (s *SQLite) StorePasswordHash(ctx context.Context, id int64, hash string) error {
	result, err := s.db.ExecContext(ctx, "UPDATE users SET password_hash=? WHERE id=?", hash, id)
	if err != nil {
		return err
	}
	count, err := result.RowsAffected()
	if err == nil && count == 0 {
		return model.ErrNotFound
	}
	return err
}
