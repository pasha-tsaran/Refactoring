package handler_test

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"sync"
	"testing"

	"example.com/refactoring/userapi/internal/handler"
	"example.com/refactoring/userapi/internal/model"
	"example.com/refactoring/userapi/internal/service"
	"example.com/refactoring/userapi/internal/store"
	"example.com/refactoring/userapi/internal/tasks"
)

func setup(t *testing.T) (http.Handler, *service.Users) {
	t.Helper()
	repo, err := store.Open(filepath.Join(t.TempDir(), "users.db"))
	if err != nil {
		t.Fatal(err)
	}
	runner := tasks.New(2, nil)
	t.Cleanup(func() {
		runner.Close()
		if err := repo.Close(); err != nil {
			t.Error(err)
		}
	})
	users := service.New(repo)
	return handler.New(users, runner, slog.New(slog.NewTextHandler(io.Discard, nil))), users
}

func call(t *testing.T, h http.Handler, method, path, body, contentType string, want int) *httptest.ResponseRecorder {
	t.Helper()
	r := httptest.NewRequest(method, path, strings.NewReader(body))
	if contentType != "" {
		r.Header.Set("Content-Type", contentType)
	}
	w := httptest.NewRecorder()
	h.ServeHTTP(w, r)
	if w.Code != want {
		t.Fatalf("%s %s status=%d want=%d body=%s", method, path, w.Code, want, w.Body.String())
	}
	return w
}

func TestUserLifecycle(t *testing.T) {
	h, _ := setup(t)
	response := call(t, h, "POST", "/adduser", `{"name":"  Анна  ","tags":["student","new","student"]}`, "application/json", 201)
	var result struct {
		Status string
		model.User
	}
	if err := json.Unmarshal(response.Body.Bytes(), &result); err != nil {
		t.Fatal(err)
	}
	if result.ID != 1 || result.Name != "Анна" || len(result.Tags) != 2 {
		t.Fatalf("user=%+v", result)
	}
	call(t, h, "GET", "/user/1", "", "", 200)
	for _, method := range []string{"GET", "POST", "GET"} {
		w := call(t, h, method, "/activate/1", "", "", 200)
		if !bytes.Contains(w.Body.Bytes(), []byte(`"active":[1]`)) {
			t.Fatal(w.Body.String())
		}
	}
	call(t, h, "POST", "/adducer", `{"name":"Legacy"}`, "application/json", 201)
	call(t, h, "GET", "/slow", "", "", 202)
	for _, path := range []string{"/health", "/docs", "/openapi.json", "/openapi.yaml"} {
		call(t, h, "GET", path, "", "", 200)
	}
	w := call(t, h, "GET", "/wrong", "", "", 500)
	if !strings.Contains(w.Body.String(), "division by zero") {
		t.Fatal(w.Body.String())
	}
}

func TestInvalidRequests(t *testing.T) {
	h, _ := setup(t)
	for _, body := range []string{
		`null`, `[]`, `{}`, `{"name":null}`, `{"name":123}`, `{"name":" "}`,
		`{"name":"ok","tags":null}`, `{"name":"ok","tags":"bad"}`,
		`{"name":"ok","tags":[null]}`, `{"name":"ok","role":"admin"}`,
		`{"name":"a\nb"}`, `{"name":"ok","tags":[" "]}`, `{`, `{} {}`,
		`{"name":"` + strings.Repeat("x", 101) + `"}`,
		`{"name":"ok","tags":["` + strings.Repeat("x", 31) + `"]}`,
	} {
		t.Run(body, func(t *testing.T) { call(t, h, "POST", "/adduser", body, "application/json", 400) })
	}
	call(t, h, "POST", "/adduser", strings.Repeat("x", 20000), "application/json", 413)
	call(t, h, "POST", "/adduser", `{"name":"a"}`, "text/plain", 415)
	for _, id := range []string{"0", "-1", "abc", "1%20OR%201=1", "9223372036854775808"} {
		call(t, h, "GET", "/user/"+id, "", "", 400)
	}
	for _, path := range []string{"/user/999", "/activate/999", "/unknown", "/user/1/extra"} {
		call(t, h, "GET", path, "", "", 404)
	}
	for _, path := range []string{"/adduser", "/adducer", "/user/1", "/activate/1", "/slow", "/wrong", "/health", "/docs", "/openapi.json", "/openapi.yaml"} {
		w := call(t, h, "DELETE", path, "", "", 405)
		if w.Header().Get("Allow") == "" {
			t.Fatal("missing Allow")
		}
	}
}

func TestSQLInjectionAndTagLimits(t *testing.T) {
	h, users := setup(t)
	ctx := context.Background()
	name := "Robert'); DROP TABLE users; --"
	tags := []string{"student"}
	user, err := users.Create(ctx, name, tags)
	if err != nil {
		t.Fatal(err)
	}
	if len(tags) != 1 {
		t.Fatal("caller tags mutated")
	}
	stored, err := users.ByName(ctx, name)
	if err != nil || stored.ID != user.ID {
		t.Fatalf("lookup: %+v %v", stored, err)
	}
	if _, err := users.ByName(ctx, "' OR 1=1 --"); err != model.ErrNotFound {
		t.Fatalf("injection lookup: %v", err)
	}
	input := map[string]any{"name": "20 tags", "tags": []string{}}
	for i := 0; i < 20; i++ {
		input["tags"] = append(input["tags"].([]string), string(rune('a'+i)))
	}
	body, err := json.Marshal(input)
	if err != nil {
		t.Fatal(err)
	}
	call(t, h, "POST", "/adduser", string(body), "application/json", 201)
	input["tags"] = append(input["tags"].([]string), "21st")
	body, err = json.Marshal(input)
	if err != nil {
		t.Fatal(err)
	}
	call(t, h, "POST", "/adduser", string(body), "application/json", 400)
}

func TestConcurrentCreationAndActivity(t *testing.T) {
	_, users := setup(t)
	var wg sync.WaitGroup
	ids := make(chan int64, 60)
	for i := 0; i < 60; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			user, err := users.Create(context.Background(), "Concurrent", nil)
			if err != nil {
				t.Error(err)
				return
			}
			ids <- user.ID
			if _, err := users.Activate(context.Background(), user.ID); err != nil {
				t.Error(err)
			}
		}()
	}
	wg.Wait()
	close(ids)
	unique := make(map[int64]bool)
	var last int64
	for id := range ids {
		unique[id] = true
		last = id
	}
	if len(unique) != 60 {
		t.Fatalf("created %d distinct users", len(unique))
	}
	snapshot, err := users.Activate(context.Background(), last)
	if err != nil || len(snapshot) != 50 {
		t.Fatalf("active %v %v", snapshot, err)
	}
	snapshot[0] = -1
	next, err := users.Activate(context.Background(), last)
	if err != nil {
		t.Fatal(err)
	}
	for _, id := range next {
		if id < 1 {
			t.Fatal("snapshot aliases shared slice")
		}
	}
}

type busy struct{}

func (busy) Schedule() bool { return false }

func TestBusyScheduler(t *testing.T) {
	_, users := setup(t)
	h := handler.New(users, busy{}, slog.Default())
	w := call(t, h, "GET", "/slow", "", "", 503)
	if w.Header().Get("Retry-After") != "1" {
		t.Fatal("missing Retry-After")
	}
}
