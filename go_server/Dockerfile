# syntax=docker/dockerfile:1
FROM golang:1.26-bookworm@sha256:5de7c99eb78ca5e515a4c340235d0955ec5964a5071c492c15503d7c267da473 AS base
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download && go mod verify
COPY . .

FROM base AS test
RUN test -z "$(gofmt -l .)" && go vet ./... \
    && go test -race -coverpkg=./internal/... -coverprofile=/tmp/coverage.out ./... \
    && go tool cover -func=/tmp/coverage.out

FROM test AS build
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/server ./cmd/server \
    && mkdir -p /out/data && chown 65532:65532 /out/data

FROM scratch AS runtime
COPY --from=build /out/server /server
COPY --from=build --chown=65532:65532 /out/data /data
USER 65532:65532
ENV HTTP_ADDR=:8080 DB_PATH=/data/users.db
EXPOSE 8080
VOLUME ["/data"]
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD ["/server", "-healthcheck"]
ENTRYPOINT ["/server"]
