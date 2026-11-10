// Package utils provides password hashing without exposing credential endpoints.
package utils

import (
	"crypto/pbkdf2"
	"crypto/rand"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/hex"
	"errors"
	"fmt"
	"strings"
)

const iterations = 600000

func HashPassword(password string) (string, error) {
	if len(password) < 8 || len(password) > 1024 {
		return "", errors.New("password must contain 8 to 1024 UTF-8 bytes")
	}
	salt := make([]byte, 16)
	if _, err := rand.Read(salt); err != nil {
		return "", err
	}
	digest, err := pbkdf2.Key(sha256.New, password, salt, iterations, 32)
	if err != nil {
		return "", err
	}
	return fmt.Sprintf("pbkdf2_sha256$%d$%x$%x", iterations, salt, digest), nil
}

func VerifyPassword(password, encoded string) bool {
	parts := strings.Split(encoded, "$")
	if len(parts) != 4 || parts[0] != "pbkdf2_sha256" || parts[1] != "600000" || len(password) < 8 || len(password) > 1024 {
		return false
	}
	salt, err := hex.DecodeString(parts[2])
	if err != nil || len(salt) != 16 {
		return false
	}
	expected, err := hex.DecodeString(parts[3])
	if err != nil || len(expected) != 32 {
		return false
	}
	actual, err := pbkdf2.Key(sha256.New, password, salt, iterations, 32)
	return err == nil && subtle.ConstantTimeCompare(actual, expected) == 1
}

// IsAdmin expects a trusted role object; it does not perform authentication.
func IsAdmin(user map[string]any) bool { return user["role"] == "admin" }
