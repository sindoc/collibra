// chip_queries.go — Go entry point for the chip MCP query surface.
//
// Reads docs/xml/chip-queries.xml (lang=XML.g()) and exposes typed structures
// compatible with singine.persistence.v1 gRPC (persistence.proto).
//
// This file is the authoritative Go representation of the XML grammar.
// Python equivalent: singine-collibra/python/singine_collibra/chip_queries.py
//
// Usage:
//
//	go run chip_queries.go [status|gen-id|jprofiler-targets]
package main

import (
	"encoding/json"
	"encoding/xml"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

// ── XML grammar types (lang=XML.g()) ─────────────────────────────────────────

type ChipQueryGrammar struct {
	XMLName       xml.Name          `xml:"chip-query-grammar"`
	Version       string            `xml:"version,attr"`
	Generated     string            `xml:"generated,attr"`
	Protocol      string            `xml:"protocol,attr"`
	EntryPoint    string            `xml:"entry-point,attr"`
	Depths        WorkspaceDepths   `xml:"workspace-depths"`
	QueryTypes    []QueryType       `xml:"query-types>query-type"`
	GrpcBindings  GrpcHttpBindings  `xml:"grpc-http-bindings"`
	JProfiler     JProfilerTargets  `xml:"jprofiler-targets"`
}

type WorkspaceDepths struct {
	Root   string          `xml:"root,attr"`
	Depths []DepthLevel    `xml:"depth"`
}

type DepthLevel struct {
	ID          string `xml:"id,attr"`
	Level       int    `xml:"level,attr"`
	Symbol      string `xml:"symbol,attr"`
	Description string `xml:"description,attr"`
}

type QueryType struct {
	ID    string `xml:"id,attr"`
	Tool  string `xml:"tool,attr"`
	Chain string `xml:"chain,attr"`
}

type GrpcHttpBindings struct {
	Service   string        `xml:"service,attr"`
	Proto     string        `xml:"proto,attr"`
	GoPackage string        `xml:"go-package,attr"`
	GrpcPort  string        `xml:"grpc-port,attr"`
	HTTPPort  string        `xml:"http-port,attr"`
	Bindings  []HTTPBinding `xml:"binding"`
}

type HTTPBinding struct {
	RPC         string `xml:"rpc,attr"`
	HTTPMethod  string `xml:"http-method,attr"`
	HTTPPath    string `xml:"http-path,attr"`
	Description string `xml:"description,attr"`
}

type JProfilerTargets struct {
	AgentPort string           `xml:"agent-port,attr"`
	Targets   []JProfilerEntry `xml:"target"`
}

type JProfilerEntry struct {
	ID                string `xml:"id,attr"`
	Runtime           string `xml:"runtime,attr"`
	MainClassPattern  string `xml:"main-class-pattern,attr"`
	ConfigKey         string `xml:"config-key,attr"`
	SnapshotDir       string `xml:"snapshot-dir,attr"`
	Implementation    string `xml:"implementation,attr"`
}

// ── Workspace depth: ~ws(self, + ++ +++ ++++ +++++) ──────────────────────────

type WorkspaceDepth int

const (
	DepthSelf    WorkspaceDepth = 0 // self
	DepthShallow WorkspaceDepth = 1 // +
	DepthMedium  WorkspaceDepth = 2 // ++
	DepthDeep    WorkspaceDepth = 3 // +++
	DepthDeeper  WorkspaceDepth = 4 // ++++
	DepthFull    WorkspaceDepth = 5 // +++++
)

// ── Code lookup request ───────────────────────────────────────────────────────

type CodeLookupRequest struct {
	Term  string         `json:"term"`
	Depth WorkspaceDepth `json:"depth"`
	Scope string         `json:"scope,omitempty"`
}

// ── Type retrieval ────────────────────────────────────────────────────────────

type TypeRef struct {
	IRI        string   `json:"type_iri"`
	TypeName   string   `json:"type_name"`
	CollibraID string   `json:"collibra_id"`
	AssetType  string   `json:"asset_type"`
	Fragments  []string `json:"fragments"`
}

type TypeRetrieval struct {
	TypeRef    TypeRef                `json:"type_ref"`
	Properties map[string]interface{} `json:"properties"`
	Relations  []map[string]interface{} `json:"relations"`
}

// ── gRPC-HTTP request ─────────────────────────────────────────────────────────

type GrpcHttpRequest struct {
	RPC     string                 `json:"rpc"`
	Body    map[string]interface{} `json:"body"`
	BaseURL string                 `json:"base_url"`
	UseHTTP bool                   `json:"use_http"`
}

// ── JProfiler target ──────────────────────────────────────────────────────────

type JProfilerTarget struct {
	ProcessID  string `json:"process_id"`
	Runtime    string `json:"runtime"`
	PID        int    `json:"pid"`
	ConfigID   string `json:"config_id"`
	AgentPort  int    `json:"agent_port"`
	AttachArgs string `json:"attach_args"`
}

// ── Grammar loader ────────────────────────────────────────────────────────────

func loadGrammar(path string) (*ChipQueryGrammar, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("reading grammar: %w", err)
	}
	var g ChipQueryGrammar
	if err := xml.Unmarshal(data, &g); err != nil {
		return nil, fmt.Errorf("parsing grammar XML: %w", err)
	}
	return &g, nil
}

// ── JVM process discovery via jps ─────────────────────────────────────────────

func discoverJVMTargets(grammar *ChipQueryGrammar) []JProfilerTarget {
	out, err := exec.Command("jps", "-l").Output()
	if err != nil {
		return nil
	}
	port, _ := strconv.Atoi(grammar.JProfiler.AgentPort)
	if port == 0 {
		port = 8849
	}

	var targets []JProfilerTarget
	for _, line := range strings.Split(string(out), "\n") {
		parts := strings.SplitN(strings.TrimSpace(line), " ", 2)
		if len(parts) < 2 {
			continue
		}
		pid, _ := strconv.Atoi(parts[0])
		mainClass := parts[1]

		for _, t := range grammar.JProfiler.Targets {
			for _, pattern := range strings.Split(t.MainClassPattern, "|") {
				if strings.Contains(mainClass, pattern) {
					targets = append(targets, JProfilerTarget{
						ProcessID:  mainClass,
						Runtime:    t.Runtime,
						PID:        pid,
						ConfigID:   t.ConfigKey,
						AgentPort:  port,
						AttachArgs: fmt.Sprintf("-agentpath:/opt/jprofiler/bin/linux-x64/libjprofilerti.so=port=%d,nowait=y,id=%s", port, t.ConfigKey),
					})
					break
				}
			}
		}
	}
	return targets
}

func repoRoot() (string, error) {
	dir, err := os.Getwd()
	if err != nil {
		return "", fmt.Errorf("get working directory: %w", err)
	}

	for {
		candidate := filepath.Join(dir, "docs", "xml", "chip-queries.xml")
		if _, err := os.Stat(candidate); err == nil {
			return dir, nil
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			return "", fmt.Errorf("could not locate repository root from %s", dir)
		}
		dir = parent
	}
}

// ── Main ──────────────────────────────────────────────────────────────────────

func main() {
	cmd := "status"
	if len(os.Args) > 1 {
		cmd = os.Args[1]
	}

	root, err := repoRoot()
	if err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		os.Exit(1)
	}
	grammarPath := filepath.Join(root, "docs", "xml", "chip-queries.xml")

	grammar, err := loadGrammar(grammarPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		os.Exit(1)
	}

	var result interface{}
	switch cmd {
	case "jprofiler-targets":
		result = map[string]interface{}{
			"ok":        true,
			"targets":   discoverJVMTargets(grammar),
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		}
	case "grpc-bindings":
		result = map[string]interface{}{
			"ok":       true,
			"service":  grammar.GrpcBindings.Service,
			"bindings": grammar.GrpcBindings.Bindings,
		}
	default:
		result = map[string]interface{}{
			"ok":           true,
			"grammar":      grammar.Version,
			"protocol":     grammar.Protocol,
			"entry_point":  grammar.EntryPoint,
			"depths":       grammar.Depths.Depths,
			"query_types":  grammar.QueryTypes,
			"jprofiler":    grammar.JProfiler.Targets,
			"grpc_service": grammar.GrpcBindings.Service,
			"timestamp":    time.Now().UTC().Format(time.RFC3339),
		}
	}

	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	enc.Encode(result) //nolint:errcheck
}
