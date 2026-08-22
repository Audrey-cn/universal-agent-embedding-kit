# Security Policy

## Supported versions

UAEK is pre-1.0 (alpha). Security fixes target the current `0.3.0.dev1`
development line on `main`; older development snapshots and releases are not
supported.

| Version / branch | Supported |
|------------------|:---------:|
| `0.3.0.dev1` / `main` | ✅ |
| older | ❌ |

## Reporting a vulnerability

**Please do not open a public issue for security problems.**

Use GitHub's private vulnerability reporting:
**Security → Report a vulnerability** on the
[repository](https://github.com/Audrey-cn/universal-agent-embedding-kit/security/advisories/new).

Please include:

- a description of the issue and its impact,
- steps to reproduce (a minimal example if possible),
- affected version / commit.

We aim to acknowledge a report within a few days and to coordinate a fix and
disclosure timeline with you.

## Execution trust boundaries

### Trusted adapters

Command-backed adapters execute commands selected by the operator. They are
trusted adapters: they inherit the caller's environment and are not subjected to
the candidate-code AST policy. UAEK bounds their runtime, memory, and combined
output and terminates their process group on timeout, but operators must only
configure commands they trust.

### Restricted candidate execution

Benchmark candidate Python is checked against a restrictive AST policy, receives
a limited builtins set, and runs in a child process with a temporary working
directory, a reduced environment, and resource, time, and output limits. These
controls reduce accidental and straightforward abuse while preserving the
benchmark API.

### Residual isolation boundary

This subprocess isolation is **not a kernel-level sandbox**. In particular, the
current `allow_network` and `allow_filesystem_write` policy fields are metadata;
they do not enforce OS-level network or filesystem isolation, and resource-limit
support varies by platform. Run untrusted scenario packs in a disposable
container or virtual machine with no credentials, sensitive mounts, or network
access. Reports about the verification or isolation path are especially welcome.
