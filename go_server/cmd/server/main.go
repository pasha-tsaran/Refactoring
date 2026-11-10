// Command server starts the HTTP service or performs a container health check.
package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"log/slog"
	"net"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"example.com/refactoring/userapi/internal/config"
	"example.com/refactoring/userapi/internal/handler"
	"example.com/refactoring/userapi/internal/service"
	"example.com/refactoring/userapi/internal/store"
	"example.com/refactoring/userapi/internal/tasks"
)

func main() {
	if err := run(); err != nil {
		slog.Error("server stopped", "error", err)
		os.Exit(1)
	}
}

func run() error {
	healthcheck := flag.Bool("healthcheck", false, "check the local HTTP service")
	flag.Parse()
	cfg, err := config.Load()
	if err != nil {
		return err
	}
	if *healthcheck {
		_, port, _ := net.SplitHostPort(cfg.Address)
		client := http.Client{Timeout: 2 * time.Second}
		response, err := client.Get("http://127.0.0.1:" + port + "/health")
		if err != nil {
			return err
		}
		defer response.Body.Close()
		if response.StatusCode != 200 {
			return fmt.Errorf("health status: %d", response.StatusCode)
		}
		return nil
	}
	repo, err := store.Open(cfg.Database)
	if err != nil {
		return err
	}
	defer repo.Close()
	runner := tasks.New(2, nil)
	defer runner.Close()
	server := &http.Server{
		Addr: cfg.Address, Handler: handler.New(service.New(repo), runner, slog.Default()),
		ReadHeaderTimeout: 5 * time.Second, ReadTimeout: 10 * time.Second,
		WriteTimeout: 15 * time.Second, IdleTimeout: 60 * time.Second,
		MaxHeaderBytes: 1 << 20,
	}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	failed := make(chan error, 1)
	go func() { failed <- server.ListenAndServe() }()
	slog.Info("listening", "address", cfg.Address)
	select {
	case err := <-failed:
		if errors.Is(err, http.ErrServerClosed) {
			return nil
		}
		return err
	case <-ctx.Done():
		shutdown, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		return server.Shutdown(shutdown)
	}
}
