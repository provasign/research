// deephard_astq: go/ast queries for the deephard Go recipes (build/deephard_recipes_go.py).
//
// Reads a JSON array of requests on stdin, writes a JSON array of answers.
// Offsets in answers are byte offsets into the file; line 0 means col is a byte offset.
//
//	{"op":"funcat","file":F,"line":L,"col":C}  the func literal starting at L:C (or the
//	                                            innermost one containing it, starting on line L)
//	{"op":"funcdecl","file":F,"name":N}         the top-level func N (no receiver)
//	{"op":"stmt","file":F,"line":L,"col":C}     the innermost statement of a block that contains L:C
//	{"op":"calls","file":F,"name":N}            every call whose callee is N or X.N
//
// A func answer: {start, params_end, has_results, lbrace, rbrace, returns:[{start,end,n}],
// last_terminating, stmts}; returns of nested func literals are excluded.
// A stmt answer: {start, end, col, funcs:[{params:[[name,type],...]}...]} innermost first.
// A call answer: {start, end, lparen, rparen, nargs, stmt_start, in_assign_lhs, ctx}
package main

import (
	"bytes"
	"encoding/json"
	"go/ast"
	"go/parser"
	"go/printer"
	"go/token"
	"os"
)

type req struct {
	Op   string `json:"op"`
	File string `json:"file"`
	Line int    `json:"line"`
	Col  int    `json:"col"`
	Name string `json:"name"`
}

type parsed struct {
	fset *token.FileSet
	f    *ast.File
	tf   *token.File
	src  []byte
}

var cache = map[string]*parsed{}

func load(path string) *parsed {
	if p, ok := cache[path]; ok {
		return p
	}
	src, err := os.ReadFile(path)
	if err != nil {
		return nil
	}
	fset := token.NewFileSet()
	f, err := parser.ParseFile(fset, path, src, parser.ParseComments)
	if f == nil {
		return nil
	}
	_ = err
	p := &parsed{fset: fset, f: f, src: src}
	fset.Iterate(func(tf *token.File) bool { p.tf = tf; return false })
	cache[path] = p
	return p
}

func (p *parsed) off(pos token.Pos) int { return p.fset.Position(pos).Offset }

func (p *parsed) pos(line, col int) token.Pos {
	if line == 0 { // col is a byte offset
		return p.tf.Pos(col)
	}
	if line < 1 || line > p.tf.LineCount() {
		return token.NoPos
	}
	return p.tf.LineStart(line) + token.Pos(col-1)
}

func (p *parsed) str(n ast.Node) string {
	var b bytes.Buffer
	printer.Fprint(&b, p.fset, n)
	return b.String()
}

func terminating(s ast.Stmt) bool {
	switch s := s.(type) {
	case *ast.ReturnStmt:
		return true
	case *ast.ExprStmt:
		if c, ok := s.X.(*ast.CallExpr); ok {
			if id, ok := c.Fun.(*ast.Ident); ok && id.Name == "panic" {
				return true
			}
			if se, ok := c.Fun.(*ast.SelectorExpr); ok {
				switch se.Sel.Name {
				case "Fatal", "Fatalf", "FailNow", "Exit", "Skip", "Skipf", "SkipNow":
					return true
				}
			}
		}
	case *ast.BlockStmt:
		return len(s.List) > 0 && terminating(s.List[len(s.List)-1])
	case *ast.IfStmt:
		if s.Else == nil {
			return false
		}
		return terminating(s.Body) && terminating(s.Else)
	case *ast.ForStmt:
		return s.Cond == nil && !hasBreak(s.Body)
	case *ast.BranchStmt:
		return s.Tok == token.GOTO
	}
	return false
}

func hasBreak(b *ast.BlockStmt) bool {
	found := false
	ast.Inspect(b, func(n ast.Node) bool {
		switch n := n.(type) {
		case *ast.FuncLit, *ast.ForStmt, *ast.RangeStmt, *ast.SwitchStmt, *ast.TypeSwitchStmt, *ast.SelectStmt:
			return false
		case *ast.BranchStmt:
			if n.Tok == token.BREAK && n.Label == nil {
				found = true
			}
		}
		return true
	})
	return found
}

func (p *parsed) funcInfo(start token.Pos, typ *ast.FuncType, body *ast.BlockStmt) map[string]any {
	rets := []map[string]any{}
	if body != nil {
		ast.Inspect(body, func(n ast.Node) bool {
			switch n := n.(type) {
			case *ast.FuncLit:
				return false
			case *ast.ReturnStmt:
				rets = append(rets, map[string]any{"start": p.off(n.Pos()), "end": p.off(n.End()), "n": len(n.Results)})
			}
			return true
		})
	}
	ans := map[string]any{
		"start":       p.off(start),
		"params_end":  p.off(typ.Params.Closing) + 1,
		"has_results": typ.Results != nil && len(typ.Results.List) > 0,
		"returns":     rets,
	}
	if body != nil {
		ans["lbrace"] = p.off(body.Lbrace)
		ans["rbrace"] = p.off(body.Rbrace)
		ans["stmts"] = len(body.List)
		ans["last_terminating"] = len(body.List) > 0 && terminating(body.List[len(body.List)-1])
	}
	return ans
}

func (p *parsed) funcat(line, col int) map[string]any {
	at := p.pos(line, col)
	var best *ast.FuncLit
	ast.Inspect(p.f, func(n ast.Node) bool {
		fl, ok := n.(*ast.FuncLit)
		if !ok {
			return true
		}
		if fl.Pos() == at {
			best = fl
			return false
		}
		if fl.Pos() <= at && at < fl.End() && p.fset.Position(fl.Pos()).Line == line {
			best = fl
		}
		return true
	})
	if best == nil {
		return nil
	}
	return p.funcInfo(best.Pos(), best.Type, best.Body)
}

func (p *parsed) funcdecl(name string) map[string]any {
	for _, d := range p.f.Decls {
		if fd, ok := d.(*ast.FuncDecl); ok && fd.Recv == nil && fd.Name.Name == name {
			return p.funcInfo(fd.Pos(), fd.Type, fd.Body)
		}
	}
	return nil
}

func (p *parsed) params(t *ast.FuncType) [][2]string {
	out := [][2]string{}
	for _, f := range t.Params.List {
		ts := p.str(f.Type)
		if len(f.Names) == 0 {
			out = append(out, [2]string{"", ts})
		}
		for _, n := range f.Names {
			out = append(out, [2]string{n.Name, ts})
		}
	}
	return out
}

// stmtAt: innermost statement that is an element of a statement list and contains at.
func (p *parsed) stmtAt(at token.Pos) map[string]any {
	var stmt ast.Stmt
	var funcs []map[string]any
	var visit func(n ast.Node) bool
	lists := func(n ast.Node) []ast.Stmt {
		switch n := n.(type) {
		case *ast.BlockStmt:
			return n.List
		case *ast.CaseClause:
			return n.Body
		case *ast.CommClause:
			return n.Body
		}
		return nil
	}
	visit = func(n ast.Node) bool {
		if n == nil || !(n.Pos() <= at && at < n.End()) {
			return false
		}
		switch fn := n.(type) {
		case *ast.FuncLit:
			funcs = append([]map[string]any{{"params": p.params(fn.Type), "start": p.off(fn.Pos()), "end": p.off(fn.End())}}, funcs...)
		case *ast.FuncDecl:
			funcs = append([]map[string]any{{"params": p.params(fn.Type), "start": p.off(fn.Pos()), "end": p.off(fn.End()), "name": fn.Name.Name}}, funcs...)
		}
		for _, s := range lists(n) {
			if s.Pos() <= at && at < s.End() {
				stmt = s
			}
		}
		return true
	}
	ast.Inspect(p.f, visit)
	if stmt == nil {
		return nil
	}
	return map[string]any{"start": p.off(stmt.Pos()), "end": p.off(stmt.End()),
		"col": p.fset.Position(stmt.Pos()).Column, "funcs": funcs}
}

func (p *parsed) calls(name string) []map[string]any {
	out := []map[string]any{}
	ast.Inspect(p.f, func(n ast.Node) bool {
		c, ok := n.(*ast.CallExpr)
		if !ok {
			return true
		}
		var id *ast.Ident
		switch f := c.Fun.(type) {
		case *ast.Ident:
			id = f
		case *ast.SelectorExpr:
			id = f.Sel
		}
		if id == nil || id.Name != name {
			return true
		}
		out = append(out, map[string]any{"start": p.off(c.Pos()), "end": p.off(c.End()),
			"lparen": p.off(c.Lparen), "rparen": p.off(c.Rparen), "nargs": len(c.Args),
			"line": p.fset.Position(c.Pos()).Line, "col": p.fset.Position(c.Pos()).Column})
		return true
	})
	return out
}

func main() {
	var reqs []req
	if err := json.NewDecoder(os.Stdin).Decode(&reqs); err != nil {
		panic(err)
	}
	out := make([]any, len(reqs))
	for i, r := range reqs {
		p := load(r.File)
		if p == nil {
			continue
		}
		switch r.Op {
		case "funcat":
			if a := p.funcat(r.Line, r.Col); a != nil {
				out[i] = a
			}
		case "funcdecl":
			if a := p.funcdecl(r.Name); a != nil {
				out[i] = a
			}
		case "stmt":
			if a := p.stmtAt(p.pos(r.Line, r.Col)); a != nil {
				out[i] = a
			}
		case "calls":
			out[i] = p.calls(r.Name)
		}
	}
	json.NewEncoder(os.Stdout).Encode(out)
}
