# Slack App Profile Update

## Confirmed identity decision

The Slack bot identity should be updated manually after the new avatar is ready.

- Set the bot display name to `Monkey Scott`.
- Replace the current avatar with `assets/avatar/monkey-scott.png`, a monkey version of the existing screaming Michael Scott avatar.
- Do not use `Gnik Gnok`.
- Do not create a second bot user or Slack app for this change.

The generated avatar is stored at `assets/avatar/monkey-scott.png` and must be uploaded manually through the Slack App/profile workflow.

## Avatar asset

The prepared avatar is available at `assets/avatar/monkey-scott.png`. It is the monkey
version of the supplied screaming Michael Scott source and must be uploaded manually.

## Manual profile-change procedure

Perform this as a manual change on the existing production Slack app; do not create a replacement app or bot user.

1. Open [Your Apps](https://api.slack.com/apps) and select the installed production app used by this bot.
2. Open the app's bot-user settings. If starting from Slack, use the workspace menu: `Tools & settings` → `Manage apps` → select the installed app → open its app settings → `Bot user`. Edit the bot display name to exactly `Monkey Scott`, then save.
3. Upload `assets/avatar/monkey-scott.png`. Do not use `Gnik Gnok` or an unrelated replacement image.
4. In the same app settings, open `Basic Information` → `Display Information` and replace the app icon/avatar with the prepared image. Save the change and confirm the preview uses the new image.
5. Open the installed bot's profile in the workspace and verify that both the display name and avatar are shown as `Monkey Scott`. Do not reinstall the app for a profile-only change; reinstall only if OAuth scopes were changed.

The runtime uses a Slack App bot token, so its posted messages inherit the Slack App's bot username and icon. Do not add runtime `username`, `icon_url`, or `chat:write.customize` overrides for this profile change.

## Permissions to verify

Verify the installed production app, not only the Slack API configuration page.

### Bot token scopes

| Scope | Why it is needed |
| --- | --- |
| `chat:write` | Posts the daily standup thread, thread replies, reminders, the closing message, escalation, and operational alerts. |
| `reactions:write` | Adds one approved custom reaction after a user's report is saved successfully. |
| `files:write` | Uploads the local GIF/PNG media used by reminders and end-of-day escalation. |
| `channels:history` | Receives and reads messages and thread history when the configured standup channel is public. |
| `groups:history` | Use this instead of `channels:history` when the configured standup channel is private. |

The bot must be a member of the standup channel and any configured alert channel. A scope does not grant access to a channel where the bot is not a member.

### App-level token

Verify `connections:write` on the app-level token used by `SLACK_APP_TOKEN`. This is required for the Slack Socket Mode connection.

Do not add profile customization scopes or unrelated scopes. The current flow does not require `chat:write.customize`, `chat:write.public`, `app_mentions:read`, or `files:read`.

If a required scope is added or changed, re-authorize/reinstall the Slack app so the installed production bot token receives the updated permission. Profile changes normally propagate without reinstalling.

## Manual post-deploy checklist

### Profile identity

- [ ] Confirm the original screaming Michael Scott source image was supplied before avatar work started.
- [ ] Update the bot display name to exactly `Monkey Scott`.
- [ ] Upload `assets/avatar/monkey-scott.png` as the bot avatar.
- [ ] Confirm a new standup message shows `Monkey Scott` and the new avatar.
- [ ] Confirm no duplicate bot user or replacement app was created.

### Connection and permissions

- [ ] Confirm the service starts in Socket Mode without `invalid_auth`, `not_in_channel`, or `missing_scope` errors.
- [ ] Confirm the installed bot token has `chat:write`, `reactions:write`, `files:write`, and the correct public/private history scope.
- [ ] Confirm the app-level token has `connections:write`.
- [ ] Confirm the bot is a member of the standup channel and configured alert channel.

### Existing message flow

- [ ] Confirm the daily standup thread is posted in the configured channel.
- [ ] Confirm a saved user report receives one approved custom reaction after persistence succeeds.
- [ ] Confirm a missing-report reminder uploads a local GIF/PNG into the active thread.
- [ ] Confirm the end-of-day escalation uploads its local GIF/PNG into the same thread.
- [ ] Confirm that a controlled media-upload failure posts the same copy as a text-only reply in the active thread.
- [ ] Confirm the text fallback does not change the bot display name or avatar.

## External-action confirmation

No Slack write API was called by this agent. No Slack UI profile change was performed. The Slack profile was not changed, no message was sent, no file was uploaded, no app was reinstalled, no deployment was performed, and no production code was edited.
