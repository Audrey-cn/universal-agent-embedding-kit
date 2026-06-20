# Security Policy

## Supported versions

UAEK is pre-1.0 (alpha). Only the latest `main` and the most recent tagged
release receive fixes.

| Version | Supported |
|---------|:---------:|
| `0.1.x` / `main` | ✅ |
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

## Scope notes

UAEK drives external agent platforms and executes graded code in its benchmarks.
Treat benchmark execution as you would any code-running sandbox: run untrusted
scenario packs only in an isolated environment. Reports about the verification or
sandboxing path are especially welcome.
