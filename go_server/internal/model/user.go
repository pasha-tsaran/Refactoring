// Package model defines public user data and input validation.
package model

import (
	"errors"
	"strconv"
	"strings"
	"unicode/utf8"
)

var ErrNotFound = errors.New("user not found")

type User struct {
	ID   int64    `json:"id"`
	Name string   `json:"name"`
	Tags []string `json:"tags"`
}

// Validate copies the tags and appends the new-user tag exactly once.
func Validate(name string, tags []string) (string, []string, error) {
	clean := strings.TrimSpace(name)
	if !utf8.ValidString(name) || utf8.RuneCountInString(clean) < 1 || utf8.RuneCountInString(name) > 100 || control(name) {
		return "", nil, errors.New("name must contain 1 to 100 characters without controls")
	}
	if len(tags) > 20 {
		return "", nil, errors.New("tags must contain at most 20 strings")
	}
	result := make([]string, 0, len(tags)+1)
	seen := make(map[string]bool)
	for _, tag := range tags {
		value := strings.TrimSpace(tag)
		if !utf8.ValidString(tag) || utf8.RuneCountInString(value) < 1 || utf8.RuneCountInString(tag) > 30 || control(tag) {
			return "", nil, errors.New("each tag must contain 1 to 30 characters without controls")
		}
		if !seen[value] {
			result = append(result, value)
			seen[value] = true
		}
	}
	if !seen["new"] {
		result = append(result, "new")
	}
	return clean, result, nil
}

func control(value string) bool {
	for _, char := range value {
		if char < 32 {
			return true
		}
	}
	return false
}

func ParseID(value string) (int64, error) {
	for _, char := range value {
		if char < '0' || char > '9' {
			return 0, errors.New("id must be a positive integer")
		}
	}
	id, err := strconv.ParseInt(value, 10, 64)
	if err != nil || id < 1 {
		return 0, errors.New("id must be a positive 64-bit integer")
	}
	return id, nil
}
