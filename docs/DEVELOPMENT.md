# Local development and hosted testing

Use one working folder for Threadly: `/Users/ananditashekhar/Downloads/apparel_agent`.
The Desktop/ApparelCare_Agent_refined folder is an older copy. Changes there do not update this repository.

## What changes where

- `app.py`: layout, customer greeting input, star ratings and chat closure.
- `agent.py`: model instructions, policy decisions, tools and response wording.
- `tests/`: checks for business behaviour and feedback flow.
- `.env`: private local configuration, excluded from Git.
- Streamlit app settings, Secrets: private hosted configuration, separate from `.env`.

Saving a file changes the local app. A commit records a version locally. A push sends commits to GitHub. Streamlit Community Cloud then redeploys the configured branch. Local secrets and the SQLite database are not pushed.

## Repeatable workflow

1. Edit this project and check the local app.
2. Run `.venv/bin/python -m unittest discover -s tests -v`.
3. Inspect `git diff` and `git status --short`.
4. Stage only intended files, then commit with a description of the behaviour changed.
5. Run `git push origin main` to publish to the deployed branch.
6. Wait for Streamlit to update, then test using a new chat. Existing transcript text does not change.

For larger experiments, work on a `codex/` branch and merge after review.

## Hosted OpenAI configuration

In Streamlit Community Cloud, open this app's Settings > Secrets. Add the following as root-level TOML values, preserving other settings. Replace the key placeholder privately in Streamlit, never in this repository:

```toml
OPENAI_API_KEY = "YOUR_PRIVATE_KEY"
OPENAI_MODEL = "gpt-5.6-luna"
APP_MODE = "OpenAI"
ALLOW_MODE_SWITCH = "false"
```

Set separate private `SUPPORT_ACCESS_CODE` and `ADMIN_ACCESS_CODE` values there too before exposing operations pages. These are prototype access codes, not production authentication. Save and restart/reboot the app if needed. Root-level Streamlit secrets are exposed as environment variables, which this code already reads.

This enables billable requests for people who can access the hosted app. Keep the key private and monitor account usage. Do not put Ollama's localhost URL in the hosted configuration expecting it to reach your Mac.

## Local Ollama

Keep local `APP_MODE=Demo` with `ALLOW_MODE_SWITCH=true` in `.env`, then select Ollama locally after installing a model and setting `OLLAMA_MODEL`. Local Ollama testing and hosted OpenAI testing can use the same committed application code. Compare models using identical datasets, dates and recorded code versions; browser trials alone are not a controlled accuracy evaluation.

## Separate agent projects

Keep the HackerRank agent in a separate folder and repository, with its own environment, credentials, tests and deployment. If both projects use Streamlit simultaneously, assign different local ports. Never copy Threadly's `.env` into another repository. Confirm the HackerRank project's framework and intended use before adapting deployment instructions.

References: https://docs.streamlit.io/develop/concepts/connections/secrets-management and https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app/app-settings
