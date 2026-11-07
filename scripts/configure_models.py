"""Configure provider credentials locally without exposing them in chat or shell history."""
from getpass import getpass
from pathlib import Path
from dotenv import dotenv_values, set_key

root = Path(__file__).resolve().parents[1]
env = root / '.env'
env.touch(mode=0o600, exist_ok=True)
env.chmod(0o600)
print('Keys are saved only in this project’s private .env file.')
print('Press Enter to keep any existing setting. Input keys are hidden.')
for provider in ('OPENAI', 'GEMINI', 'GROQ'):
    key = getpass(f'{provider} API key (Enter to skip): ').strip()
    if key:
        set_key(str(env), provider + '_API_KEY', key)
        current = dotenv_values(env).get(provider + '_MODEL', '')
        model = input(f'{provider} model ID [{current}]: ').strip()
        if model:
            set_key(str(env), provider + '_MODEL', model)
print('Saved. Restart the app and choose a provider under Demo settings.')
input('Press Enter to close this window.')
