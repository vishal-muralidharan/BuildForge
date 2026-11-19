# README styles

Pick 1 style per project. Every style has a clear target audience, goal, structure, and tone.

| Style | Used by | Audience |
|---|---|---|
| `showcase` | BitHab, Humane, Liefde, NeMo, TeNo, PP | Visitors, recruiters, users |
| `minimal` | Portfolio | You and quick visitors |
| `technical` | Razorpay Buildathon | Developers and reviewers |
| `api` | BuildForge | People who use the tool |

---

## 1. Showcase (apps people use)

The goal is to make a visitor understand and want the app in 30 seconds.

- Title and a 1 line pitch.
- Live link and a screenshot or GIF.
- Features: 5 to 8 bullets, each about what the user gets.
- Tech stack.
- Getting started: prerequisites, install, env variable names, run.
- Scripts: dev, test, lint, build.
- Tests: how to run them and what they cover.
- Project structure: short.
- Deployment: where it runs and how.
- Author and license.

**Tone:** confident, benefits first. The first screen sells the app, and the setup comes after.

### Showcase emoji pattern

Put 1 emoji at the start of each feature line, chosen for meaning, not decoration:

```markdown
## Features

- 💸 **Track spending** in seconds, with categories you control.
- 📊 **See where money goes** with monthly charts.
- 🔒 **Private by default.** Your data stays in your account.
```

Keep emojis out of commands, code blocks, and table headers.

---

## 2. Minimal (small sites)

The goal is to say what it is and how to run it, in about 30 lines.

- Title and 1 line.
- Live link.
- How to run or edit it locally.
- How it deploys.
- License.

Leave out feature lists, architecture, and structure trees.

---

## 3. Technical (fullstack or backend)

The goal is for a developer to understand how it works and run every part.

- Overview: the problem and the solution.
- Architecture: components, data flow, a diagram or short description.
- Tech stack, with the reason for each choice.
- Setup for each part, such as backend and frontend, and env variable names.
- How to run and how to test.
- API endpoints: a short table.
- Data model.
- Key decisions and tradeoffs.
- Known limits.
- Deployment.

**Tone:** precise and complete. Write for someone who will change the code.

---

## 4. API (CLI or library)

The goal is for a user to install it and succeed in 2 minutes.

- What it is, in 1 line.
- Install: 1 command.
- Quick start: 1 example that works when pasted.
- Commands and options: a table.
- Configuration.
- Examples for common tasks.
- Output and exit codes.
- Version support and compatibility.
- Upgrading, with a link to the changelog.
- Troubleshooting.
- Contributing, security policy, license.

**Tone:** exact and scannable. Use code blocks that can be copied.

---

## Other common types

- **Library or package:** like API, plus a short reference of the public functions and the install for each package manager.
- **Monorepo or docs hub:** a map of the folders, what each one does, and how to run all of them.
- **Profile README (GitHub profile):** who you are, what you work on, links. Keep it short.
- **Data or research:** the question, the data source, the method, how to reproduce the results, the limits.
- **Template or starter:** what you get, how to use the template, and what to change first.
- **Course or final year project:** the problem, the approach, the results, how to run, and the team.

---

## Rules for every README

- The first screen answers what it is, why it matters, and how to start.
- Every command works exactly as written.
- Every command and script matches package.json or the project card.
- Links are relative and point to files that exist. No file:/// links and no local paths such as /Users/....
- Show env variable names only. Never show values or secrets.
- Take every fact from the code. Do not invent features.
- Update the README when a feature changes.
