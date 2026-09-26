# run_e2e pinned-runtime shell (see runners/run_e2e.py _agent_env).
# Load the user's real .zshrc, then put the pinned toolchains back in front:
# the login shell's path_helper and the profile push /opt/homebrew/bin ahead
# of whatever PATH the harness passed in, and Claude Code snapshots THIS
# PATH for every Bash tool call.
[ -f "$HOME/.zshrc" ] && source "$HOME/.zshrc"
[ -n "$E2E_PINNED_PATH" ] && export PATH="$E2E_PINNED_PATH:$PATH"
