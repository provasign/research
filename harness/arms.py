"""Tool arms for the study (design §4).

Each arm is a frozen configuration of the agent: a tool allowlist enforced by
the `claude` CLI (not merely requested in the prompt -- design §10 guards
against tool-effort imbalance) plus an arm-specific guidance block appended to
the shared Mode-A instruction.

  T  text-only          rg/grep/find/read. No graph. The baseline.
  G  graph-primitives   prism for traversal; grep only to find an anchor.
  G* graph-change-impact  prism change-impact delivers the full change-set in
                        ONE call; the agent just parses the result.
  V  graph-as-verifier  text-primary, then verify completeness with the graph
                        before asserting `complete: true`.

The graph arms drive prism through the *CLI* (Bash), not MCP: a session's MCP
server can't be hot-swapped and is shared across subagents (see the project
memory on MCP staleness), so the CLI is the only way to pin the exact binary
per run. `PRISM_BIN` selects it (default: the released ~/bin/prism; set it to a
primitives build such as /tmp/prism-prim to exercise resolve/edges).
"""
from __future__ import annotations

import os
from dataclasses import dataclass

PRISM_BIN = os.environ.get("PRISM_BIN", os.path.expanduser("~/bin/prism"))

# Shared across every arm: the task framing and the machine-scorable output
# contract. The ONLY per-arm difference is the tools + the guidance block, so
# the tool dimension is isolated (design §7, paired design).
#
# {lang} / {site_example} are filled per task language so a Java agent is not
# told it is reading Go. The Go fill reproduces the original prompt byte-for-byte
# (lang="Go", site_example="response_writer.go:Hijack") so the existing Go runs
# stay comparable.
BASE_PROMPT = """\
You are answering a code-context question about a {lang} repository. This is a \
LOCALIZATION / IMPACT analysis task, NOT a coding task: do NOT edit, write, or \
patch any file. Investigate the repository and determine the complete set of \
functions/methods that must be CHANGED to fix the issue below.

ISSUE:
{prompt}

When you are done, output ONLY a single JSON object on its own, exactly in \
this shape (no prose after it):

{{
  "sites": ["<relpath>:<Symbol>", ...],   // every function/method that must change
  "complete": true | false,                // true ONLY if you are confident the list is exhaustive
  "unresolved": ["<what you could not resolve and why>", ...]  // ambiguous/undetermined edges; [] if none
}}

Use the form "<repo-relative-path>:<FunctionOrMethodName>" for each site \
(receiver optional, e.g. "{site_example}"). Be precise: a missed \
site is a broken fix, and a false site wastes a reviewer's time. Set \
"complete" honestly -- if dynamic dispatch or anything else leaves you unsure \
you found every site, set it false and list what is unresolved.
"""

# Per-language fills. Keys are the task `lang` field (lowercased); "go" must
# reproduce the historical prompt exactly. The lookup example feeds G/V guidance
# so the graph arm is told the correct prism symbol syntax for the language.
LANG_PROFILE: dict[str, dict[str, str]] = {
    "go": {"name": "Go", "site_example": "response_writer.go:Hijack",
           "lookup_example": "pkg.FuncName"},
    "java": {"name": "Java",
             "site_example": "StringUtils.java:join",
             "lookup_example": "org.apache.commons.lang3.StringUtils#join"},
}


def lang_profile(lang: str) -> dict[str, str]:
    return LANG_PROFILE.get((lang or "go").lower(), LANG_PROFILE["go"])

T_GUIDANCE = """\
TOOLS: you have ripgrep/grep/find/sed and file reads only. Locate the relevant \
code by searching for symbols and strings, read the surrounding code, and \
reason about which functions a fix must touch."""

G_GUIDANCE = """\
TOOLS: you have the `prism` call-graph CLI plus ripgrep (use ripgrep only to \
FIND an anchor symbol; use prism to TRAVERSE from it). prism reports authoritative \
file:line -- do not re-grep what it returns. Useful commands:
  {prism} query "<task>" --terms a,b --include graph,tests --format text   # callers/callees/tests of seeds
  {prism} lookup <{lookup_example}> --format text                          # one function body/signature
  {prism} read <file> --format text                                        # whole file
  {prism} references <Name> --format text                                  # where a symbol is used
Trace callers and dispatch targets through the graph to find every site a fix \
must touch; the graph -- not grep -- is how you confirm completeness."""

GSTAR_GUIDANCE = """\
TOOLS: you have the `prism change-impact` command, which returns the COMPLETE \
change-set for a method signature change in one call: the declaration(s), every \
override/implementation in the subtype closure (family), and every resolved \
call site (callers). Your workflow:

1. Read the issue and identify the TYPE and METHOD being changed.
2. Run ONE command:
     {prism} change-impact 'Type.method(ParamType, ...)' .
   Use the exact type and method name from the issue. Include param types for \
precision (e.g. 'JsonSerializer.serialize(T, JsonGenerator, SerializerProvider)').
   If you are not sure of the exact param types, omit them: 'Type.method' also works.
3. Parse the JSON output. The result has five groups:
   - declarations:   the method itself (must change)
   - family:         every override/implementation in the subtype closure (must change)
   - callers:        every resolved call site (must change)
   - declaringTypes: interface/type declaration blocks whose member signatures \
must change (must change — report each as "<file>:<TypeName>")
   - supers:         same-member declarations on other contracts (must change too)
4. Union declarations + family + callers + declaringTypes (+ supers if they are \
separate methods) and output those as your sites list.

Do NOT manually hunt for overrides or search for callers — the graph computed \
the full traversal for you. If you need to confirm the exact type name before \
running change-impact, use `{prism} search <Name>`; do not use any other search \
tool. Relay the result directly into your answer without re-filtering or augmenting."""

V_GUIDANCE = """\
TOOLS: you have ripgrep/grep/find/sed/read AND the `prism` call-graph CLI. \
Work text-FIRST: find the candidate change-sites with ripgrep and reading. \
Then, BEFORE you set "complete": true, VERIFY completeness with the graph -- \
run prism to enumerate callers/dispatch targets of each candidate and confirm \
you have not missed a site:
  {prism} query "<task>" --terms a,b --include graph,tests --format text
  {prism} references <Name> --format text
If the graph reveals sites grep missed, add them; if it leaves something \
unresolved, record it in "unresolved" and set "complete": false."""


@dataclass
class Arm:
    name: str
    allowed_tools: list[str]  # passed to `claude --allowedTools`
    guidance: str

    def prompt(self, task_prompt: str, lang: str = "go") -> str:
        prof = lang_profile(lang)
        return (
            BASE_PROMPT.format(
                prompt=task_prompt, lang=prof["name"],
                site_example=prof["site_example"],
            )
            + "\n\n"
            + self.guidance.format(
                prism=PRISM_BIN, lookup_example=prof["lookup_example"],
            )
        )


_TEXT_BASH = [
    "Bash(rg:*)",
    "Bash(grep:*)",
    "Bash(find:*)",
    "Bash(sed:*)",
    "Bash(cat:*)",
    "Bash(ls:*)",
    "Bash(head:*)",
    "Bash(tail:*)",
    "Bash(wc:*)",
]
_PRISM_BASH = ["Bash(prism:*)", f"Bash({PRISM_BIN}:*)"]

ARMS: dict[str, Arm] = {
    "T": Arm("T", ["Read", "Grep", "Glob", *_TEXT_BASH], T_GUIDANCE),
    # G: graph-primary. Keep rg available solely for the anchor-find step the
    # prism workflow prescribes; traversal must go through prism.
    "G": Arm("G", ["Read", "Glob", "Bash(rg:*)", *_PRISM_BASH], G_GUIDANCE),
    # G*: one high-altitude call to change-impact; agent just reads the result.
    # rg removed: prism search covers the only legitimate pre-call use (type-name
    # lookup). Removing rg structurally enforces relay -- the agent cannot augment
    # the engine answer with text search.
    "Gstar": Arm("Gstar", [*_PRISM_BASH], GSTAR_GUIDANCE),
    "V": Arm("V", ["Read", "Grep", "Glob", *_TEXT_BASH, *_PRISM_BASH], V_GUIDANCE),
}
