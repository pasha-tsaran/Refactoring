package store_test

import (
	"context"
	"errors"
	"path/filepath"
	"testing"

	"example.com/refactoring/userapi/internal/model"
	"example.com/refactoring/userapi/internal/store"
)

func TestPersistenceAndMissingUser(t *testing.T) {
	path := filepath.Join(t.TempDir(), "users.db")
	repo, err := store.Open(path)
	if err != nil {
		t.Fatal(err)
	}
	user, err := repo.Add(context.Background(), "Persistent", []string{"new"})
	if err != nil {
		t.Fatal(err)
	}
	if err := repo.StorePasswordHash(context.Background(), user.ID, "test-hash"); err != nil {
		t.Fatal(err)
	}
	if err := repo.StorePasswordHash(context.Background(), 999, "hash"); !errors.Is(err, model.ErrNotFound) {
		t.Fatalf("missing user: %v", err)
	}
	if err := repo.Close(); err != nil {
		t.Fatal(err)
	}
	reopened, err := store.Open(path)
	if err != nil {
		t.Fatal(err)
	}
	defer reopened.Close()
	stored, err := reopened.Get(context.Background(), user.ID)
	if err != nil || stored.Name != "Persistent" || stored.Tags[0] != "new" {
		t.Fatalf("stored=%+v err=%v", stored, err)
	}
}
