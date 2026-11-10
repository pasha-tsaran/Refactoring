package utils_test

import (
	"strings"
	"testing"

	"example.com/refactoring/userapi/internal/utils"
)

func TestPasswordHashAndVerification(t *testing.T) {
	hash, err := utils.HashPassword("correct-password")
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(hash, "correct-password") || !utils.VerifyPassword("correct-password", hash) || utils.VerifyPassword("wrong-password", hash) {
		t.Fatal("password verification failed")
	}
	other, err := utils.HashPassword("correct-password")
	if err != nil || other == hash {
		t.Fatal("salt reused")
	}
	if _, err := utils.HashPassword("short"); err == nil {
		t.Fatal("short password accepted")
	}
	for _, bad := range []string{"", "broken", "pbkdf2_sha256$999999999$x$x"} {
		if utils.VerifyPassword("correct-password", bad) {
			t.Fatal("bad hash accepted")
		}
	}
	if utils.IsAdmin(nil) || utils.IsAdmin(map[string]any{"role": []string{"admin"}}) || !utils.IsAdmin(map[string]any{"role": "admin"}) {
		t.Fatal("role must fail closed")
	}
}
