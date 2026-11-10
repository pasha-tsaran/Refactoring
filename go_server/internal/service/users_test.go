package service_test

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"path/filepath"
	"strings"
	"testing"

	"example.com/refactoring/userapi/internal/model"
	"example.com/refactoring/userapi/internal/service"
	"example.com/refactoring/userapi/internal/store"
	"example.com/refactoring/userapi/internal/utils"
)

func TestStoredPasswordIsHashedAndNeverPublic(t *testing.T) {
	path := filepath.Join(t.TempDir(), "users.db")
	repo, err := store.Open(path)
	if err != nil {
		t.Fatal(err)
	}
	defer repo.Close()
	users := service.New(repo)
	ctx := context.Background()
	user, err := users.Create(ctx, "Password user", nil)
	if err != nil {
		t.Fatal(err)
	}
	if err := users.StorePassword(ctx, user.ID, "correct-password"); err != nil {
		t.Fatal(err)
	}
	if err := users.StorePassword(ctx, user.ID, "short"); err == nil {
		t.Fatal("short password accepted")
	}
	if err := users.StorePassword(ctx, 999, "correct-password"); !errors.Is(err, model.ErrNotFound) {
		t.Fatalf("missing user: %v", err)
	}
	db, err := sql.Open("sqlite", path)
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	var encoded string
	if err := db.QueryRow("SELECT password_hash FROM users WHERE id=?", user.ID).Scan(&encoded); err != nil {
		t.Fatal(err)
	}
	if !utils.VerifyPassword("correct-password", encoded) || strings.Contains(encoded, "correct-password") {
		t.Fatal("unsafe stored password")
	}
	public, err := users.Get(ctx, user.ID)
	if err != nil {
		t.Fatal(err)
	}
	data, err := json.Marshal(public)
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(data), encoded) || strings.Contains(string(data), "password") {
		t.Fatal("password leaked in public model")
	}
}
