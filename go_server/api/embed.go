// Package api embeds the contract and documentation in the server binary.
package api

import _ "embed"

//go:embed openapi.json
var JSON []byte

//go:embed openapi.yaml
var YAML []byte

//go:embed docs.html
var Docs []byte
