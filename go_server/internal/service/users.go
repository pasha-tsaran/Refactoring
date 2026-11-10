// Package service contains application rules independent of HTTP.
package service

import (
	"context"
	"sync"

	"example.com/refactoring/userapi/internal/model"
	"example.com/refactoring/userapi/internal/utils"
)

type Repository interface {
	Add(context.Context, string, []string) (model.User, error)
	Get(context.Context, int64) (model.User, error)
	ByName(context.Context, string) (model.User, error)
	StorePasswordHash(context.Context, int64, string) error
	Ping(context.Context) error
}

type Users struct {
	repo   Repository
	mu     sync.Mutex
	active []int64
}

func New(repo Repository) *Users { return &Users{repo: repo, active: []int64{}} }

func (s *Users) Create(ctx context.Context, name string, tags []string) (model.User, error) {
	name, tags, err := model.Validate(name, tags)
	if err != nil {
		return model.User{}, err
	}
	return s.repo.Add(ctx, name, tags)
}

func (s *Users) Get(ctx context.Context, id int64) (model.User, error) { return s.repo.Get(ctx, id) }
func (s *Users) ByName(ctx context.Context, name string) (model.User, error) {
	return s.repo.ByName(ctx, name)
}
func (s *Users) Ping(ctx context.Context) error { return s.repo.Ping(ctx) }

func (s *Users) Activate(ctx context.Context, id int64) ([]int64, error) {
	if _, err := s.repo.Get(ctx, id); err != nil {
		return nil, err
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	for i, previous := range s.active {
		if previous == id {
			s.active = append(s.active[:i], s.active[i+1:]...)
			break
		}
	}
	s.active = append(s.active, id)
	if len(s.active) > 50 {
		s.active = s.active[len(s.active)-50:]
	}
	return append([]int64{}, s.active...), nil
}

func (s *Users) StorePassword(ctx context.Context, id int64, password string) error {
	if _, err := s.repo.Get(ctx, id); err != nil {
		return err
	}
	hash, err := utils.HashPassword(password)
	if err != nil {
		return err
	}
	return s.repo.StorePasswordHash(ctx, id, hash)
}
