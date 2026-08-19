# Installing the Package

The Release Coordinator is packaged as a normal Python project. During local
development, install it in editable mode from the repository root:

```powershell
cd C:\Users\seime\PythonProject\ai-release-coordinator
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Editable mode keeps the installed package connected to the source checkout, so
code changes are picked up without reinstalling.

## Build a Wheel

Install the build tool:

```powershell
.\.venv\Scripts\python.exe -m pip install build
```

Build the package:

```powershell
.\.venv\Scripts\python.exe -m build
```

The build writes distribution files to `dist/`, for example:

```text
dist/
- ai_release_coordinator-1.0.0-py3-none-any.whl
- ai_release_coordinator-1.0.0.tar.gz
```

`dist/` is generated output and should not be committed.

## Install the Built Wheel Somewhere Else

Copy the wheel to another environment and install it with pip:

```powershell
python -m pip install .\dist\ai_release_coordinator-1.0.0-py3-none-any.whl
```

After installation, the package can be used through Python modules:

```powershell
python -m release_agent.cli --help
python -m uvicorn release_agent.api:app --host 0.0.0.0 --port 8010
```

If the console scripts are installed, these commands are also available:

```powershell
release-coordinator --help
release-coordinator-api
```

## Runtime Configuration

Set a read-only GitHub token before collecting evidence or running the preview
API:

```powershell
$env:GITHUB_TOKEN="your-read-only-token"
```

Optional dashboard settings:

```powershell
$env:RELEASE_AGENT_DATABASE_URL="postgresql://user:password@localhost:5432/database"
$env:RELEASE_AGENT_PREVIEW_WEBHOOK_URL="http://localhost:5678/webhook/release-agent-preview"
$env:RELEASE_AGENT_REVIEW_WEBHOOK_URL="http://localhost:5678/webhook/release-agent-review-decision"
```

Optional API entry-point settings:

```powershell
$env:RELEASE_COORDINATOR_HOST="0.0.0.0"
$env:RELEASE_COORDINATOR_PORT="8010"
$env:RELEASE_COORDINATOR_RELOAD="true"
```
