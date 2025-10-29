import os
import subprocess

# Your Heroku app name
HEROKU_APP_NAME = "whisone-backend"

# Read environment variables from your local .env file
def load_env_file(env_path=".env"):
    env_vars = {}
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                if "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip().strip('"').strip("'")
    return env_vars

def set_heroku_env(env_vars):
    for key, value in env_vars.items():
        if value == "":
            print(f"⚠️  Skipping empty variable: {key}")
            continue
        print(f"⬆️  Setting {key}...")
        HEROKU_PATH = r"C:\Program Files\Heroku\bin\heroku.exe"
        print(HEROKU_PATH)

        subprocess.run([
            HEROKU_PATH, "config:set", f"{key}={value}", "-a", HEROKU_APP_NAME
        ], check=False)

if __name__ == "__main__":
    print("🚀 Loading .env file...")
    env = load_env_file(".env")

    if not env:
        print("❌ No environment variables found in .env file.")
    else:
        print(f"✅ Found {len(env)} variables.")
        set_heroku_env(env)
        print("\n🎉 Done! All environment variables have been pushed to Heroku.")
