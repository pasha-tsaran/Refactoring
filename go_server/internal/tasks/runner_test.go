package tasks_test

import (
	"context"
	"testing"

	"example.com/refactoring/userapi/internal/tasks"
)

func TestBoundedRunnerAndShutdown(t *testing.T) {
	runner := tasks.New(1, func(ctx context.Context) { <-ctx.Done() })
	if !runner.Schedule() || runner.Schedule() {
		t.Fatal("concurrency limit not enforced")
	}
	runner.Close()
	if runner.Schedule() {
		t.Fatal("closed runner accepted work")
	}
	if tasks.LongRunningTask(context.Background(), 10) != 285 {
		t.Fatal("incorrect calculation")
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if tasks.LongRunningTask(ctx, 100000) != 0 {
		t.Fatal("cancellation ignored")
	}
}
