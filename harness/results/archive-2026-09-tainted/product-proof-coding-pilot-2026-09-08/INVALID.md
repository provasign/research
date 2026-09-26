# Invalid comparison

Do not combine this run with product-proof results.

Dependency installation generated `src/urllib3/_version.py` in the native
template after the Prism template had already been copied. The resulting
urllib3 native and Prism workspaces were not content-equivalent: native had the
generated module and Prism did not. This asymmetry was discovered during the
post-run transcript and filesystem audit.

The replacement run is `../product-proof-coding-pilot-fixed-2026-09-08` and was
created only after adding a prepared-template content-parity assertion.
