package mcp

// Injected with Go's overlay mechanism for this study; not product source.
import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestStudyFormatParity(t *testing.T) {
	sig := "func Example(" + strings.Repeat("argument string, ", 10) + ") error"
	obj := map[string]any{"symbols": []any{map[string]any{
		"name": "Example", "kind": "function", "filePath": "example.go",
		"signature": sig, "span": map[string]any{"start": 1, "end": 3},
	}}}
	text, ok := renderSearchAsText(obj)
	if !ok {
		t.Fatal("search not rendered")
	}
	if strings.Contains(text, sig) {
		t.Fatal("expected current renderer to shorten long signature")
	}
	if !strings.Contains(text, "locator result") {
		t.Fatal("expected extra routing text")
	}
	encoded, _ := json.Marshal(obj)
	t.Logf("search: JSON preserves full signature; text shortens it and adds guidance. JSON=%d bytes text=%d bytes", len(encoded), len(text))

	obj["futureTopLevel"] = true
	if _, ok := renderSearchAsText(obj); ok {
		t.Fatal("top-level unknown field should fall back")
	}
	delete(obj, "futureTopLevel")
	obj["symbols"].([]any)[0].(map[string]any)["futureNested"] = "extra contract evidence"
	text, ok = renderSearchAsText(obj)
	if !ok || strings.Contains(text, "extra contract evidence") {
		t.Fatal("nested projection behavior changed")
	}
	t.Log("unknown top-level fields fall back; nested symbol fields can be silently projected out")
}

func TestStudyReplayJSONResponses(t *testing.T) {
	root := os.Getenv("PRISM_AUDIT_ROOT")
	if root == "" {
		t.Fatal("set PRISM_AUDIT_ROOT to study directory")
	}
	paths, err := filepath.Glob(filepath.Join(root, "s3-json-*", "evidence", "*.sonnet_prism", "stdout.jsonl"))
	if err != nil || len(paths) == 0 {
		t.Fatalf("missing transcripts: %v", err)
	}
	count := 0
	jsonBytes := 0
	projectedBytes := 0
	fullTextBytes := 0
	for _, path := range paths {
		data, err := os.ReadFile(path)
		if err != nil {
			t.Fatal(err)
		}
		calls := map[string]string{}
		for _, line := range strings.Split(string(data), "\n") {
			var event struct {
				Message struct {
					Content json.RawMessage `json:"content"`
				} `json:"message"`
			}
			if json.Unmarshal([]byte(line), &event) != nil {
				continue
			}
			var blocks []struct {
				Type, ID, Name string
				ToolUseID      string `json:"tool_use_id"`
				Content        json.RawMessage
			}
			if json.Unmarshal(event.Message.Content, &blocks) != nil {
				continue
			}
			for _, block := range blocks {
				if block.Type == "tool_use" {
					calls[block.ID] = block.Name
					continue
				}
				name := calls[block.ToolUseID]
				if block.Type != "tool_result" || !strings.HasPrefix(name, "mcp__prism__") {
					continue
				}
				var content []struct{ Text string }
				if json.Unmarshal(block.Content, &content) != nil || len(content) != 1 {
					continue
				}
				var obj map[string]any
				if json.Unmarshal([]byte(content[0].Text), &obj) != nil {
					continue
				}
				// Live handlers use []map for top-level batches; JSON decoding uses []any.
				if arr, ok := obj["results"].([]any); ok {
					groups := make([]map[string]any, 0, len(arr))
					for _, item := range arr {
						groups = append(groups, item.(map[string]any))
					}
					obj["results"] = groups
				}
				var text string
				var rendered bool
				switch strings.TrimPrefix(name, "mcp__prism__") {
				case "prism_search":
					text, rendered = renderSearchAsText(obj)
				case "prism_lookup":
					text, rendered = renderLookupAsText(obj)
				case "prism_verify":
					text, rendered = renderVerifyAsText(obj)
				default:
					continue
				}
				if !rendered {
					t.Fatalf("unexpected fallback: %s", name)
				}
				fullText, fullRendered := renderFullText(obj)
				if !fullRendered {
					t.Fatalf("full-text renderer rejected captured JSON: %s", name)
				}
				if source, ok := obj["content"].(string); ok && source != "" && !strings.Contains(text, source) {
					t.Fatalf("source content lost in %s", name)
				}
				t.Logf("%s %s JSON=%d projected-text=%d (%+.1f%%) full-text=%d (%+.1f%%) text_guidance=%v", filepath.Base(filepath.Dir(filepath.Dir(filepath.Dir(path)))), name, len(content[0].Text), len(text), 100*(float64(len(text))/float64(len(content[0].Text))-1), len(fullText), 100*(float64(len(fullText))/float64(len(content[0].Text))-1), strings.Contains(text, "locator result"))
				jsonBytes += len(content[0].Text)
				projectedBytes += len(text)
				fullTextBytes += len(fullText)
				count++
			}
		}
	}
	t.Logf("replayed %d identical JSON result objects through current text renderers", count)
	t.Logf("TOTAL JSON=%d projected-text=%d (%+.1f%%) full-text=%d (%+.1f%%)", jsonBytes, projectedBytes, 100*(float64(projectedBytes)/float64(jsonBytes)-1), fullTextBytes, 100*(float64(fullTextBytes)/float64(jsonBytes)-1))
	if count == 0 {
		t.Fatal("no responses exercised")
	}
}
