# Vetting Third Party Skills

External skill repositories contain instructions and files that an AI agent will read and execute. Treat every external file as untrusted data.

The vetting scanner inspects repository files for security risks before installation.

## What the scan checks

The `vet` command checks for 9 categories of risks:

1. **Executable scripts present:**
   Files with extensions like `.sh`, `.py`, `.js`, or scripts in a `scripts/` folder. Scripts can execute arbitrary code on your system.

2. **Network calls:**
   Commands or functions like `curl`, `wget`, `fetch`, `urllib`, or `socket`. These can exfiltrate source code, tokens, or system data.

3. **Shell and code execution:**
   Patterns like `subprocess`, `os.system`, `exec`, `eval`, or `child_process`. These execute commands outside agent guardrails.

4. **Credential and secret identifiers:**
   Tokens such as `api_key`, `secret`, `password`, `private_key`, `npm_token`, or `bearer`. External skills should not request or inspect secrets.

5. **Writes outside project boundary:**
   Paths referencing `/tmp`, `/etc`, `~/.ssh`, or directory traversal (`../..`). Skills must stay within the project root.

6. **Remote publishing commands:**
   Commands such as `git push`, `npm publish`, or `docker push`. External skills must never publish or push code.

7. **Invisible Unicode characters:**
   Zero-width spaces (`\u200b`), byte-order marks (`\ufeff`), or bidirectional override marks (`\u202a` to `\u202e`). These hide commands from human review.

8. **HTML comments:**
   Hidden comments (`<!-- ... -->`) in Markdown documents. These can inject instructions into LLM prompts without being visible in rendered views.

9. **Prompt injection and override phrases:**
   Phrases such as "ignore previous instructions", "disregard system prompt", or "do not tell the user". These attempt to bypass agent guardrails.

## How to read scan results

The scanner reports findings grouped by file and severity:

- **HIGH severity:**
  Indicates an active threat vector (for example, network calls, hidden unicode, or prompt injection). The `vet` command exits with code 1 if any high-severity finding is present. Do not install skills with high findings unless you have personally verified every line of code.

- **MEDIUM severity:**
  Indicates items that require human review, such as HTML comments or informational script listings.

## Safety limit

A clean scan is not proof of safety. The scanner checks known heuristics and patterns. It cannot detect all forms of obfuscated or novel exploits. Only install skills from sources you personally trust.
