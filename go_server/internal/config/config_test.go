package config_test

import (
	"testing"

	"example.com/refactoring/userapi/internal/config"
)

func TestConfiguration(t *testing.T) {
	t.Setenv("HTTP_ADDR", "")
	t.Setenv("DB_PATH", "")
	cfg, err := config.Load()
	if err != nil || cfg.Address != ":8080" || cfg.Database != "data/users.db" {
		t.Fatalf("config %+v %v", cfg, err)
	}
	for _, address := range []string{"oops", ":0", ":65536", ":abc"} {
		t.Setenv("HTTP_ADDR", address)
		if _, err := config.Load(); err == nil {
			t.Fatalf("accepted %q", address)
		}
	}
}
