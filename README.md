# Dify Slack Bot

A Slack bot utilizing the Dify API.

[![GitHub](https://img.shields.io/github/license/langgenius/dify)](https://github.com/langgenius/dify)
[![GitHub stars](https://img.shields.io/github/stars/langgenius/dify)](https://github.com/langgenius/dify/stargazers)
[![GitHub issues](https://img.shields.io/github/issues/langgenius/dify)](https://github.com/langgenius/dify/issues)

## Overview

This project provides a Slack bot that interacts with the Dify API to enhance your Slack workspace with powerful features.

## Getting Started

### Prerequisites

- [Slack API](https://api.slack.com/apps) account
- Dify environment
- Python 3.x installed

### Installation

**1. Clone the repository:**

```sh
git clone https://github.com/langgenius/dify_slack_bot.git
cd dify_slack_bot
```

**2. Install dependencies:**
`sh
    pip install -r requirements.txt
    `

## Setup

### 1. Slack Configuration

#### 1-1. Create a Slack App

**1. Create a new Slack app**

- Navigate to the Slack API page and create a new app.
- Click Create New App -> From scratch, then set the App Name and workspace.

**2. Configure OAuth & Permissions**

- Go to the "OAuth & Permissions" menu.
- In the "Scopes" section, add the necessary permissions under "Bot Token Scopes" (e.g., commands, chat:write).
- Click "Install App to Workspace" to install the app in your workspace.

#### 1-2. Configure Slash Commands

**1. Add a Slash Command**

- In the app settings, go to the "Slash Commands" menu.
- Click "Create New Command" and fill in the following details:
  - Command: The slash command to use (e.g., /dify)
  - Request URL: The endpoint URL that will handle the command
  - Short Description: A brief description of the command
  - Usage Hint: Example usage of the command (optional)
- Click "Save" to save the command.

**2. Test the Slash Command**

- In your Slack workspace, enter the slash command to ensure it works correctly.

#### 1-3. Configure Event Subscriptions

**1. Enable Event Subscriptions**

- In the app settings, go to the "Event Subscriptions" menu.
- Toggle the "Enable Events" switch to on.

**2. Set the Request URL**

- Enter the endpoint URL that will receive events in the "Request URL" field.
- Slack will send a verification request to this URL. Ensure your server responds correctly to verify the URL.
- [Reference1](https://api.slack.com/events/url_verification), [Reference2](https://stackoverflow.com/questions/70391828/slack-app-error-new-request-url-your-url-didnt-respond-with-the-value-of-the)

      ```python
      if slack_data.get('type') == 'url_verification':
          slack_data = request.get_json()
          challenge = slack_data.get('challenge')
          response = make_response(f"challenge={challenge}", 200)
          response.headers['Content-Type'] = 'application/x-www-form-urlencoded'
          return response
      ```

  **3. Subscribe to Bot Events**

- In the "Subscribe to Bot Events" section, add the events your bot will listen to.
- `25/01/22`, only `app_mention` is required.

**4. Configure OAuth & Permissions**

- Go to the "OAuth & Permissions" menu.
- In the "Scopes" section, add the necessary permissions under "Bot Token Scopes".
- `25/01/22`, the required scopes are `chat:write`, `channels:read`, `channels:history`, `incoming-webhook`, `im:history`
- Click "Install App to Workspace" to install the app in your workspace.

**5. Test Events**

- Trigger events in your Slack workspace to ensure they are received correctly.
- For example, send a message in a channel to verify the bot receives the event.

## Contributing

Contributions are welcome! Please read the contributing guidelines first.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

Dify
Slack API

```
Feel free to open an issue or submit a pull request if you have any questions or suggestions.
```
