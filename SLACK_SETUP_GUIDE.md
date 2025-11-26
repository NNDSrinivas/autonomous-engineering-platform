# Get Your Slack Bot Token

## Step 1: Install App to Your Workspace

1. **Go to your Slack app**: https://api.slack.com/apps/A09TM9MG95J/oauth

2. **Click "Install to Workspace"** (or "Reinstall App" if you see that)

3. **Authorize the app** - Slack will ask you to authorize the bot in your workspace

4. **Copy the Bot Token** - After installation, you'll see:
   ```
   Bot User OAuth Token: xoxb-9939327553188-7870...
   ```

## Step 2: Set Environment Variable

```bash
# Set the bot token (replace with your actual token)
export AEP_SLACK_BOT_TOKEN=xoxb-your-actual-bot-token-here

# Or add it to your shell profile for persistence
echo 'export AEP_SLACK_BOT_TOKEN=xoxb-your-token-here' >> ~/.zshrc
source ~/.zshrc
```

## Step 3: Test the Integration

```bash
# Run the setup test script
cd "/Users/mounikakapa/Desktop/Personal Projects/autonomous-engineering-platform"
python setup_slack_integration.py
```

## Your App Details (for reference):
- **App ID**: A09TM9MG95J  
- **Client ID**: 9932030018053.9939327553188
- **Client Secret**: 03e77ec4868835fac38c4b0326eeacda *(already configured)*
- **Signing Secret**: 7bb75994894637e40e142044a15f144b *(already configured)*

## What Happens Next:

Once you set the bot token, NAVI will be able to:
- ✅ List all channels in your Slack workspace
- ✅ Fetch recent messages from those channels  
- ✅ Include Slack messages in organizational memory
- ✅ Use Slack context when answering questions

This means NAVI will know about discussions, decisions, and context from your Slack workspace!