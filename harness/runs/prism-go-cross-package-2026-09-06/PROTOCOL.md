# Protocol: imported Go interface contracts

## Question

Does Grove recover an implementation of an embedded interface method when the
interface and implementation live in different project packages, without
adding a wrong-signature method or materially increasing ordinary index time?

## Arms

- `before`: Prism commit recorded in the manifest, linked to a source archive
  of Grove `184f8a9e`.
- `after`: the same Prism commit, linked to Grove `8dad4547`.

Both binaries are rebuilt locally. No model is invoked.

## Accuracy fixture

Create a fresh module with `api`, `impl`, and unrelated `util` packages. The
API interface embeds `http.CloseNotifier`; `impl.Writer` has the exact method
and asserts the contract; `impl.Wrong` returns `chan bool` instead of
`<-chan bool`. Query `Writer.CloseNotify` scoped to `api/api.go` after a fresh
index in each arm.

The before arm may either return an incomplete inventory or fail to root the
query; preserve its return code and stderr verbatim. Pass requires the after
arm to return the API declaration and caller, add exactly the real
`impl.Writer.CloseNotify` family site, exclude `impl.Wrong.CloseNotify`, and
keep the result marked partial.

## Cost guard

Fresh-index the same archive of the Prism repository six times per arm. Arm
order alternates each trial. Preserve all wall-clock samples, binary hashes,
archive hash, and final index payload. Timing is descriptive, not a release
gate; this small local sample cannot establish a performance improvement.

## Claims excluded

This replay measures deterministic engine inventory and local index time. It
does not measure autonomous task accuracy, model tokens, or session cost.
