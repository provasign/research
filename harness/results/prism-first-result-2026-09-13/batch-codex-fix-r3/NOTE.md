# batch-codex-fix-r3

The sixth planned cell of `../batch-codex-fix/` (`urllib3__urllib3__pr3786`, trial 3, Codex first-result build), which
never ran because run B crashed after five cells (see the harness commit 44a05ccc). Run separately on 2026-09-13 10:41 EDT
from run B's own copy of the binary, so the Prism sha256 is identical; the runner sha differs because the harness crash fix
had been committed in between. Its cell key is `r1` inside this run dir -- files are kept byte-identical; it is trial 3 of the
new-build sample only by composition in `../investigation/README.md`.

prism: prism dev  sha256 680df17d2371f875fe94d249dab285042b032f1fe79ac33c93f8ac8b7983bb72
runner sha256: c069ed8c2c7c66e4783d65fd637771e368c1b8333a148cad131329282d9f092e
