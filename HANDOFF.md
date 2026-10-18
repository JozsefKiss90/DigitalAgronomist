# Handoff: Digital Agronomist + OpenCode setup

For **Dr Rositsa Cholakova**, from József Kiss, October 2026.

This guide sets up the same AI-assisted development environment József tested, so you can develop
Digital Agronomist on your own machine. It assumes **Windows** with only **Git** and **VS Code**
installed. Everything else is installed below. Allow about 30–45 minutes.

---

## 1. What is in this repository

| Branch | Contents |
|---|---|
| `main` | The application source: `DigitalAgronomist_GOLD_FIXED_SQLite_EXE.py` (the whole app), the PyInstaller runtime hook, `requirements.txt`, `build_exe.bat` and this handoff. |
| `opencode-experiments` | The same code **plus** the OpenCode configuration: `opencode.json` (Ponytail plugin + Headroom MCP), `AGENTS.md` (Graphify rules for the agent) and `.opencode/plugins/graphify.js`. |

The source code was recovered from `DigitalAgronomist.exe` and checked against the original compiled
code (it compiles to identical bytecode). The original code comments could not be recovered. See `README.md`.

**Tools in the setup:**

| Tool | What it does |
|---|---|
| **OpenCode** | An AI coding agent that runs in the terminal (VS Code's terminal works). |
| **Matt Pocock's skills** | Ready-made workflows such as `/grill-me`, `tdd`, `diagnosing-bugs` and `code-review`. |
| **Ponytail** (plugin) | Keeps the agent's code small and simple. Adds `/ponytail-review`, `/ponytail-audit` and other commands. |
| **Graphify** (plugin + skill) | Builds a local map of the code so the agent looks things up instead of searching file by file. |
| **Headroom** (MCP server) | Compresses long outputs (logs, big files) so you use fewer tokens. |
| **CodeBurn** | A dashboard that shows where your tokens and money went. It runs separately from OpenCode. |

---

## 2. Install the prerequisites

Open **PowerShell** (Start menu → "PowerShell") and run these three commands:

```powershell
winget install OpenJS.NodeJS.LTS
winget install astral-sh.uv
winget install Python.Python.3.14
```

- **Node.js** runs OpenCode, the skills installer and CodeBurn.
- **uv** installs the Python-based tools (Graphify and Headroom).
- **Python 3.14** runs the app. It is the version the original exe was built with.

**Close PowerShell and open a new window** so the new commands are found, then run:

```powershell
uv tool update-shell
```

Close and reopen PowerShell once more, then check the versions:

```powershell
node -v      # v22.20 or newer
uv --version
py -3.14 --version
git --version
```

If any of them says "not recognized", restart the computer and try again.

---

## 3. Get the code (fork, then clone)

A **fork** is your own copy of the repository on GitHub. You can change it freely, and József's copy stays unchanged.

1. Sign in to GitHub and open https://github.com/JozsefKiss90/DigitalAgronomist
2. Click **Fork**. **Untick "Copy the main branch only"** so you also get the `opencode-experiments` branch.
3. Clone your fork. Replace `<your-username>` with your GitHub username:

```powershell
mkdir C:\Code -ErrorAction SilentlyContinue
cd C:\Code
git clone https://github.com/<your-username>/DigitalAgronomist
cd DigitalAgronomist
git remote add upstream https://github.com/JozsefKiss90/DigitalAgronomist
git switch opencode-experiments
```

The `upstream` remote lets you pull József's later changes with `git fetch upstream`.

Open the folder in VS Code (`code .`). You can run all the remaining commands in VS Code's own
terminal (**Terminal → New Terminal**). It opens PowerShell in the project folder.

**Tip:** for your own work, make a new branch rather than working on `main` directly, for example
`git switch -c feature/csv-export`.

---

## 4. Check that the app runs

```powershell
py -3.14 -m pip install -r requirements.txt
py -3.14 DigitalAgronomist_GOLD_FIXED_SQLite_EXE.py
```

The window should open with three tabs: "Parcel map", "Platform data" and "Local censors data".
The map needs internet access.

The app keeps its data in `water_parcel_data.sqlite3` next to the script.

---

## 5. Install OpenCode

```powershell
npm install -g opencode-ai
```

Open a new terminal and check it with `opencode --version`.

**Stay on OpenCode 1.x for now.** This setup was tested on 1.19. When OpenCode shows
"`/update` to upgrade to OpenCode 2.0", ignore it, because the Ponytail plugin uses a different
config format on 2.0.

If `opencode` is "not recognized" after a new terminal, run `npm config get prefix` and add the
folder it prints (usually `C:\Users\<you>\AppData\Roaming\npm`) to your user PATH.

---

## 6. Connect an AI model

Start OpenCode from the project folder:

```powershell
cd C:\Code\DigitalAgronomist
opencode
```

You can use either option, or both:

- **Free models:** OpenCode includes some free models (for example "Big Pickle"). They need no
  account and are good for simple tasks and for testing the setup.
- **ChatGPT Plus/Pro subscription (your own account):** type `/connect` → **OpenAI** →
  **ChatGPT Pro/Plus (browser)**. Sign in in the browser window that opens, then return to the terminal.
  Choose **browser**, not headless. Headless is only for machines without a browser.

Switch models any time with `/models`.

**Checking your ChatGPT allowance:** Plus has a 5-hour limit and a weekly limit. Check them at
**https://chatgpt.com/codex/settings/usage**. When you hit a limit, switch to a free model until it resets.

---

## 7. Install the skills, plugins and MCP

Quit OpenCode first (**Ctrl+C**). Run the commands from the project folder.

### 7.1 Matt Pocock's skills (global, installed once per computer)

```powershell
npx skills@latest add mattpocock/skills -g -a opencode
```

Accept the defaults and make sure `setup-matt-pocock-skills` is selected.

The skills **do not show up in the `/` menu**. That is normal. Ask for them by name ("Use the grill-me
skill on…"), and the agent also picks some up by itself (`tdd`, `diagnosing-bugs`). To make the
interactive ones available as `/` commands, run this once:

```powershell
$skills = 'grill-me','grill-with-docs','ask-matt','triage','improve-codebase-architecture',
          'setup-matt-pocock-skills','to-spec','to-tickets','implement','implement-spec',
          'wayfinder','retro','handoff','teach','to-questionnaire','wait-what'
$dir = "$HOME\.config\opencode\commands"
New-Item -ItemType Directory -Force $dir | Out-Null
foreach ($s in $skills) {
  Set-Content -Encoding utf8 "$dir\$s.md" @"
---
description: Run the $s skill
---
Load the ``$s`` skill with the skill tool and follow its instructions. `$ARGUMENTS
"@
}
```

### 7.2 Graphify (code map)

```powershell
uv tool install graphifyy
graphify opencode install
git status
```

The package name `graphifyy` has two y's. That is correct.

The `opencode-experiments` branch already contains Graphify's `AGENTS.md` section and plugin. The
install command adds the Graphify **skill** to your computer, and it may rewrite those two repo files.
If `git status` shows them as changed, restore the committed versions:

```powershell
git checkout -- AGENTS.md .opencode
```

Graphify can also use an AI service to name groups and read documents, but it needs an API key for that,
and the code map doesn't need it. To stop it trying to borrow another AI tool, set this once:

```powershell
setx GRAPHIFY_BACKEND none
```

Open a new terminal after `setx`.

### 7.3 Headroom (MCP server)

```powershell
uv tool install --python 3.13 "headroom-ai[all]"
```

It is a large download (about 160 packages) and takes a few minutes. If it fails while compiling
(Rust errors), use the prebuilt package instead:

```powershell
uv tool install --python 3.13 "headroom-ai[all]" --only-binary headroom-ai
```

You don't need to configure anything else. `opencode.json` on this branch already starts Headroom as an MCP server.

### 7.4 Ponytail (plugin)

Nothing to install. `opencode.json` lists `@dietrichgebert/ponytail`, and OpenCode downloads it the first
time it starts.

### 7.5 CodeBurn (usage dashboard)

You don't install this into OpenCode. Run it in a separate terminal whenever you want to see usage:

```powershell
npx codeburn
```

### 7.6 Keep generated files out of Git

```powershell
Add-Content .gitignore "graphify-out/"
```

---

## 8. Check that everything works

Start `opencode` in the project folder and go through this list:

| Check | How | Expected |
|---|---|---|
| Model | Look at the line under the prompt | Shows your chosen model |
| Headroom MCP | Type `/mcp` | `headroom connected ✓ Enabled` |
| Ponytail | Type `/ponytail` | `/ponytail`, `-review`, `-audit`, `-debt`, `-gain`, `-help` appear |
| Skills | Ask *"List the skills you have available."* | Matt Pocock's skills and `graphify` are listed |
| Graphify | Type `/graphify .` | Creates `graphify-out/` with `graph.html` and `GRAPH_REPORT.md` |
| CodeBurn | After a few prompts, run `npx codeburn` in another terminal | Your OpenCode sessions are listed |

To look at the code map: `start graphify-out\graph.html` opens an interactive map in the browser.
`graphify-out\GRAPH_REPORT.md` is a short written overview. You can also ask the graph directly:

```powershell
graphify query "Which functions write to the SQLite database?"
graphify explain "MainWindow"
graphify path "parse_kml_file" "save_parcel"
```

---

## 9. Everyday use

**Ponytail.** It is always on and makes the agent prefer the smallest change that works.

- `/ponytail` sets how strict it is: `lite`, `full` (the default) or `ultra`. Use `ultra` for small fixes, and `off` when you want a bigger restructure.
- `/ponytail-review` reviews your uncommitted changes. Run it before every commit.
- `/ponytail-audit` gives a quality report for the whole repo. It is a good first step.
- `/ponytail-debt` collects shortcuts and TODOs into a list.
- `/ponytail-gain` shows its impact so far.

**Headroom.** The agent uses it when it meets big outputs. You can also ask for it, for example:
*"Use headroom to compress the output of `git log -p` and summarise it."*
The app is small, so expect modest savings here.

**Graphify.** After you change code, run `graphify update .`, or ask the agent to. This keeps the map
current, uses only local processing and costs no tokens.

**A suggested routine for each change:**

1. Create a branch: `git switch -c feature/<name>`.
2. Optionally, describe the change and let the agent question you first: `/grill-me <what you want>`.
3. Ask OpenCode to make the change.
4. Run the app (section 4) and check the result.
5. Run `/ponytail-review`.
6. `git add` → `git commit` → `git push`.
7. Every so often, run `npx codeburn` and check the ChatGPT usage page.

**Example first prompt:**

> *"Use the graph to find where KML files are parsed, then use the diagnosing-bugs skill to check what
> happens with a KML file that has no polygons. Don't change code, just report."*

---

## 10. Troubleshooting

| Problem | Fix |
|---|---|
| `… is not recognized as the name of a cmdlet` | Open a new terminal. If that doesn't help, restart Windows. For `opencode` see section 5, for `graphify` or `headroom` run `uv tool update-shell`. |
| `npm warn EBADENGINE … required node >=22.20` | Update Node: `winget upgrade OpenJS.NodeJS.LTS`, or run the LTS installer from nodejs.org. |
| `headroom` shows **failed** in `/mcp` | Run `headroom --help` in a new terminal. If that works, restart OpenCode. |
| Ponytail commands missing | Start with `opencode --print-logs` and look for "ponytail" errors. Make sure you're on OpenCode 1.x and in the project folder. |
| Graphify says "no LLM API key found" | Run `/graphify . --code-only`, or set `GRAPHIFY_BACKEND` as in section 7.2. |
| ChatGPT models stop answering | You've reached a usage limit. Check chatgpt.com/codex/settings/usage and use a free model meanwhile. |
| Agent made unwanted changes | `git restore .` discards uncommitted changes. Only commit what you have reviewed. |

**Avoid** starting OpenCode with `headroom wrap opencode`. That routes all model traffic through Headroom,
and it isn't confirmed to work with a ChatGPT subscription login. The MCP setup above is enough.

---

## Links

- OpenCode docs: https://opencode.ai/docs/
- Matt Pocock's skills: https://github.com/mattpocock/skills
- Ponytail: https://github.com/DietrichGebert/ponytail
- Graphify for OpenCode: https://graphify.com/integrations/opencode
- Headroom: https://github.com/headroomlabs-ai/headroom
- CodeBurn: https://github.com/getagentseal/codeburn
