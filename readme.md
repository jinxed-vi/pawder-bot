# pawder bot

## Prerequisites

[Create a discord bot](https://discordpy.readthedocs.io/en/stable/discord.html).

Make sure the bot you create has the "Server Members" and "Message Content" intents.

Navigate to `https://discord.com/developers/applications/YOUR_BOT_ID/bot` to update it.

Add your bot token to your environment

```bash
# cd into the project's folder
cd pawder-bot/

export TOKEN="YOUR_DISCORD_TOKEN"
# Alternatively, using a .env file
echo "TOKEN=YOUR_DISCORD_TOKEN" > .env
```

```bash
pip install -r requirements.txt
```

## Run the bot

```bash
python3 main.py
```
