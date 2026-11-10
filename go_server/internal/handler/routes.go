// Package handler translates HTTP requests to service operations.
package handler

import (
	"encoding/json"
	"errors"
	"io"
	"log/slog"
	"mime"
	"net/http"
	"strings"
	"unicode/utf8"

	"example.com/refactoring/userapi/api"
	"example.com/refactoring/userapi/internal/model"
	"example.com/refactoring/userapi/internal/service"
)

const maxBody = 16384

type Scheduler interface{ Schedule() bool }

type API struct {
	users  *service.Users
	tasks  Scheduler
	logger *slog.Logger
}

func New(users *service.Users, tasks Scheduler, logger *slog.Logger) http.Handler {
	a := &API{users: users, tasks: tasks, logger: logger}
	return http.HandlerFunc(a.route)
}

func writeJSON(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(value); err != nil {
		slog.Warn("write response", "error", err)
	}
}

func failure(w http.ResponseWriter, status int, code string) {
	writeJSON(w, status, map[string]string{"error": code})
}

func method(w http.ResponseWriter, r *http.Request, allowed ...string) bool {
	for _, value := range allowed {
		if r.Method == value || (r.Method == "HEAD" && value == "GET") {
			return true
		}
	}
	list := append([]string{}, allowed...)
	for _, value := range allowed {
		if value == "GET" {
			list = append(list, "HEAD")
		}
	}
	w.Header().Set("Allow", strings.Join(list, ", "))
	failure(w, 405, "method_not_allowed")
	return false
}

func (a *API) route(w http.ResponseWriter, r *http.Request) {
	defer func() {
		if value := recover(); value != nil {
			a.logger.Error("request panic", "panic", value)
			failure(w, 500, "internal_error")
		}
	}()
	switch r.URL.Path {
	case "/health":
		if !method(w, r, "GET") {
			return
		}
		if err := a.users.Ping(r.Context()); err != nil {
			a.internal(w, err)
			return
		}
		writeJSON(w, 200, map[string]string{"status": "ok"})
	case "/adduser", "/adducer":
		if method(w, r, "POST") {
			a.add(w, r)
		}
	case "/slow":
		if !method(w, r, "GET") {
			return
		}
		if !a.tasks.Schedule() {
			w.Header().Set("Retry-After", "1")
			failure(w, 503, "busy")
			return
		}
		writeJSON(w, 202, map[string]string{"status": "scheduled"})
	case "/wrong":
		if method(w, r, "GET") {
			writeJSON(w, 500, map[string]string{"msg": "error", "detail": "division by zero"})
		}
	case "/openapi.json", "/openapi.yaml", "/docs":
		if !method(w, r, "GET") {
			return
		}
		body, contentType := api.JSON, "application/json"
		if r.URL.Path == "/openapi.yaml" {
			body, contentType = api.YAML, "application/yaml"
		}
		if r.URL.Path == "/docs" {
			body, contentType = api.Docs, "text/html; charset=utf-8"
		}
		w.Header().Set("Content-Type", contentType)
		if _, err := w.Write(body); err != nil {
			a.logger.Warn("write documentation", "error", err)
		}
	default:
		if strings.HasPrefix(r.URL.Path, "/user/") {
			a.user(w, r, false)
			return
		}
		if strings.HasPrefix(r.URL.Path, "/activate/") {
			a.user(w, r, true)
			return
		}
		failure(w, 404, "not_found")
	}
}

func (a *API) internal(w http.ResponseWriter, err error) {
	a.logger.Error("request failed", "error", err)
	failure(w, 500, "internal_error")
}

func (a *API) add(w http.ResponseWriter, r *http.Request) {
	contentType, _, err := mime.ParseMediaType(r.Header.Get("Content-Type"))
	if err != nil || contentType != "application/json" {
		failure(w, 415, "unsupported_media_type")
		return
	}
	body, err := io.ReadAll(http.MaxBytesReader(w, r.Body, maxBody))
	if err != nil {
		var tooLarge *http.MaxBytesError
		if errors.As(err, &tooLarge) {
			failure(w, 413, "body_too_large")
		} else {
			failure(w, 400, "invalid_json")
		}
		return
	}
	var fields map[string]json.RawMessage
	if !utf8.Valid(body) || json.Unmarshal(body, &fields) != nil {
		failure(w, 400, "invalid_json")
		return
	}
	if fields == nil {
		failure(w, 400, "invalid_input")
		return
	}
	for key := range fields {
		if key != "name" && key != "tags" {
			failure(w, 400, "invalid_input")
			return
		}
	}
	var name string
	if string(fields["name"]) == "null" || json.Unmarshal(fields["name"], &name) != nil {
		failure(w, 400, "invalid_input")
		return
	}
	tags := []string{}
	if raw, ok := fields["tags"]; ok {
		if string(raw) == "null" || json.Unmarshal(raw, &tags) != nil {
			failure(w, 400, "invalid_input")
			return
		}
		// A null element must not be silently converted to an empty string.
		if tags == nil {
			failure(w, 400, "invalid_input")
			return
		}
	}
	_, _, err = model.Validate(name, tags)
	if err != nil {
		failure(w, 400, "invalid_input")
		return
	}
	user, err := a.users.Create(r.Context(), name, tags)
	if err != nil {
		a.internal(w, err)
		return
	}
	writeJSON(w, 201, struct {
		Status string `json:"status"`
		model.User
	}{"ok", user})
}

func (a *API) user(w http.ResponseWriter, r *http.Request, activate bool) {
	prefix := "/user/"
	if activate {
		prefix = "/activate/"
	}
	value := strings.TrimPrefix(r.URL.Path, prefix)
	if value == "" || strings.Contains(value, "/") {
		failure(w, 404, "not_found")
		return
	}
	allowed := []string{"GET"}
	if activate {
		allowed = append(allowed, "POST")
	}
	if !method(w, r, allowed...) {
		return
	}
	id, err := model.ParseID(value)
	if err != nil {
		failure(w, 400, "invalid_input")
		return
	}
	if activate {
		active, err := a.users.Activate(r.Context(), id)
		if err != nil {
			a.userError(w, err)
			return
		}
		writeJSON(w, 200, map[string]any{"status": "ok", "active": active})
		return
	}
	user, err := a.users.Get(r.Context(), id)
	if err != nil {
		a.userError(w, err)
		return
	}
	writeJSON(w, 200, user)
}

func (a *API) userError(w http.ResponseWriter, err error) {
	if errors.Is(err, model.ErrNotFound) {
		failure(w, 404, "not_found")
	} else {
		a.internal(w, err)
	}
}
