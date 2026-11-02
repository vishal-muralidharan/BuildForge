# Agent Compatibility

Build Forge uses the open Agent Skills standard and the AGENTS.md instruction format.

Skills live in 1 place: `.agents/skills` in your project root. For agents that scan a different folder or read a tool-specific instruction file, Build Forge creates symlinks and pointer files.

## Compatibility Matrix

| Agent | Project Skills Folder | Reads .agents/skills | Reads AGENTS.md | Pointer File | Link Needed | Source URL | Status |
|---|---|---|---|---|---|---|---|
| Claude Code | `.claude/skills` | No | Fallback | `CLAUDE.md` | Yes | https://docs.anthropic.com/en/docs/agents-and-tools/claude-code | Unverified |
| OpenAI Codex | `.agents/skills` | Yes | Yes | None | No | https://platform.openai.com/docs | Unverified |
| Gemini CLI | `.gemini/skills` | Yes | Yes | `GEMINI.md` | Optional | https://cloud.google.com/gemini | Unverified |
| GitHub Copilot | `.github/skills` | Yes | Yes | `.github/copilot-instructions.md` | Optional | https://docs.github.com/en/copilot | Unverified |
| Cursor | `.cursor/skills` | Yes | Yes | `.cursorrules` | Optional | https://docs.cursor.com | Unverified |
| Windsurf | `.windsurf/skills` | Yes | Yes | `.windsurfrules` | Optional | https://docs.codeium.com/windsurf | Unverified |

## Manual Verification Checklist

Follow these steps to verify compatibility with any agent:

1. **Install in a scratch repository:**
   Run `npx @v1006/build-forge install` in a clean temporary repository. If your agent requires folder linking, run `npx @v1006/build-forge link`.

2. **List skills:**
   Ask your agent to list its available skills. Confirm that `project-bootstrap` appears in the list.

3. **Bootstrap:**
   Run `project-bootstrap` on a small codebase. Confirm that `.agents/project-profile.yaml` validates with 0 errors and `AGENTS.md` is generated.

4. **Deliver a change:**
   Run `feature-delivery` on a trivial change (such as adding a helper function). Confirm that the audit, plan, test, commit, and report steps finish.

5. **Record results:**
   Record the agent version, operating system, test date, and result.

## Known Limits

- **Agents without shell access:** Build Forge skills run validation and discovery scripts using Python 3. Agents that cannot run shell commands cannot execute these scripts.
- **Agents without skills support:** Agents that do not load skills dynamically rely entirely on `AGENTS.md`. You must instruct the agent to read each skill file by hand.
- **Generic skill names:** Pipeline skill names (such as `atomic-commits` or `feature-delivery`) are generic. They can collide with existing skills in your agent configuration.
