// Package tasks runs bounded, cancellable demo background jobs.
package tasks

import (
	"context"
	"sync"
)

type Runner struct {
	ctx    context.Context
	cancel context.CancelFunc
	slots  chan struct{}
	work   func(context.Context)
	mu     sync.Mutex
	closed bool
	wg     sync.WaitGroup
}

func New(limit int, work func(context.Context)) *Runner {
	ctx, cancel := context.WithCancel(context.Background())
	if work == nil {
		work = func(ctx context.Context) { LongRunningTask(ctx, 100000) }
	}
	return &Runner{ctx: ctx, cancel: cancel, slots: make(chan struct{}, limit), work: work}
}

func (r *Runner) Schedule() bool {
	r.mu.Lock()
	defer r.mu.Unlock()
	if r.closed {
		return false
	}
	select {
	case r.slots <- struct{}{}:
	default:
		return false
	}
	r.wg.Add(1)
	go func() {
		defer r.wg.Done()
		defer func() { <-r.slots }()
		r.work(r.ctx)
	}()
	return true
}

func (r *Runner) Close() {
	r.mu.Lock()
	r.closed = true
	r.cancel()
	r.mu.Unlock()
	r.wg.Wait()
}

func LongRunningTask(ctx context.Context, n int64) int64 {
	var result int64
	for i := int64(0); i < n && i < 100000; i++ {
		if i%1024 == 0 {
			select {
			case <-ctx.Done():
				return result
			default:
			}
		}
		result += i * i
	}
	return result
}
