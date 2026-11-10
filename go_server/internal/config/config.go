// Package config loads and validates environment configuration.
package config

import (
	"errors"
	"net"
	"os"
	"strconv"
)

type Config struct {
	Address  string
	Database string
}

func Load() (Config, error) {
	address := os.Getenv("HTTP_ADDR")
	if address == "" {
		address = ":8080"
	}
	_, port, err := net.SplitHostPort(address)
	if err != nil {
		return Config{}, errors.New("HTTP_ADDR must have host:port format")
	}
	number, err := strconv.Atoi(port)
	if err != nil || number < 1 || number > 65535 {
		return Config{}, errors.New("invalid HTTP_ADDR port")
	}
	path := os.Getenv("DB_PATH")
	if path == "" {
		path = "data/users.db"
	}
	return Config{Address: address, Database: path}, nil
}
