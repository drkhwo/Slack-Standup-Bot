# Revised Copy Proposal

This document contains the exact English copy for the Slack Standup Bot. It keeps the existing cool, edgy Slackbot voice and adds occasional, restrained Monkey Business references.

## Formatting conventions

- `{OPENING_PHRASE}` is replaced with one exact phrase from the 26-item opening-phrase list below.
- `{MENTIONS}` is the existing space-separated Slack mention string for the relevant users.
- `{MISSING_COUNT}` is the existing numeric count of missing reporters.
- `{TODAY_PLAN}` is the extracted `Today` section from the previous workday's report.
- `{FULL_PREVIOUS_POST}` is the existing truncated fallback text from the previous workday's report.
- `<THREAD_LINK|...>` uses the existing generated daily-thread URL and Slack link syntax.
- Text inside `*asterisks*` is Slack bold. Text inside `_underscores_` is Slack italic.
- Keep the existing team-group mentions after the opening phrase, the existing dynamic user mentions in reminders and escalation, and `<@U068KKKNP9R>` unchanged.
- Reminder and escalation media is uploaded separately in the same thread. The media URL must not be appended to these text strings.

## Daily thread opening phrases

Use one of these exact phrases as the opening line of the daily standup thread. The banana is added
once after the team mentions in the main standup post, not randomly inside the phrases.

1. `Morning. Standup is open — keep it short, useful, and on the record.`
2. `New day, same thread. What shipped, what is next, and what is in the way?`
3. `Status window open. Facts first; side quests in subthreads.`
4. `Standup is live. Drop the signal, skip the director's cut.`
5. `Quick status check: done, next, blocked.`
6. `The thread is live. Bring updates, not suspense.`
7. `Morning sync starts here. If the plan changed, write it down.`
8. `Standup is open. Keep it sharp and actionable.`
9. `What shipped? What's next? What needs a hand?`
10. `Daily status thread is live. Give us the useful version.`
11. `No mystery, just status: yesterday, today, blockers.`
12. `Status check-in is open. Concise is a feature.`
13. `Thread unlocked. ETA changes and blockers belong here.`
14. `Keep it factual, keep it moving, keep the blockers visible.`
15. `13:00 is the deadline. The thread is the source of truth.`
16. `One thread, three questions: yesterday, today, blockers.`
17. `Standup is live. Keep the status here; move the debate to subthreads.`
18. `Drop the update while it is still fresh.`
19. `Monkey see, monkey do: make the status visible. 🐒`
20. `Support your local monkey business: post the update before 13:00. 🐒`

### Emoji-inspired opening variants

Use these six as additional exact alternatives for `{OPENING_PHRASE}`. They are restrained references
to the available emoji concepts; the aliases in parentheses are internal and are not sent to Slack.

21. *(tired-monke)* `Low battery, high signal. Drop the useful version.`
22. *(investigating)* `Case file open: what shipped, what is next, what is stuck?`
23. *(ship)* `Ship check: what moved, what is next, what is stuck?`
24. *(flow-state)* `Flow state starts with a clean status.`
25. *(monkey-business)* `Monkey business, minus the mystery.`
26. *(enough-for-today)* `Need a quick win? Start with the status.`

## Main daily standup prompt

Post this exact message in the channel. Preserve the existing team-group mentions immediately after the opening phrase and the existing mention at the end.

```text
{OPENING_PHRASE} <!subteam^S074DP77Q9H> <!subteam^S08EJBE5Q4X> <!subteam^S0BHNJ7J12M> 🍌

*Daily status thread*
*Reply in the active thread before 13:00 with:*
*Yesterday:* what shipped or merged. If this continues yesterday's work, quote your previous update and add the current status.
*Today:* what you will complete today and, if relevant, how many days remain.
*Blockers / Risks:* who or what you need to unblock you.
*Keep status in this thread; move discussions to subthreads.*
*If something will not be finished today, state the remaining time.*

cc: <@U068KKKNP9R>
```

## Vacation Tracker status replies

### Vacation status unavailable

```text
⚠️ _Vacation Tracker is unavailable, so today's leave status is unknown. Monkey Business continues, but we will not guess who is out._
```

### One or more users are out

```text
🌴 *Out today — confirmed by Vacation Tracker:* {MENTIONS}
Enjoy the PTO. We'll keep the status thread moving.
```

### No users are out

```text
*Full team today:* Vacation Tracker reports no absences. Let's keep the status moving.
```

## Daytime missing-report reminders

Post the selected text as a reply in the active daily thread, replacing `{MENTIONS}` with the existing missing-user mentions. Upload the selected prepared media asset separately in the same thread.

1.

```text
Hey {MENTIONS} — your standup update is still missing. Reply in this thread with Yesterday, Today, and Blockers/Risks before 13:00.
```

2.

```text
Hey {MENTIONS} — quick nudge: the thread is still waiting on Yesterday, Today, and Blockers/Risks. Please post before 13:00.
```

3.

```text
Hey {MENTIONS} — no update from you yet. Add Yesterday, Today, and Blockers/Risks here before 13:00.
```

4.

```text
Hey {MENTIONS} — the thread is missing your update. Keep it brief: Yesterday, Today, Blockers/Risks. Deadline: 13:00.
```

5.

```text
Hey {MENTIONS} — make the status visible. Reply here with Yesterday, Today, and Blockers/Risks before 13:00. 🐒
```

6.

```text
Hey {MENTIONS} — support your local monkey business and drop your update here before 13:00: Yesterday, Today, and Blockers/Risks.
```

## Thread-closed messages

Post one of these exact messages as a reply in the active daily thread:

1.

```text
*Standup closed for today.*
Please use tomorrow's fresh thread for new updates.
```

2.

```text
*Thread closed.*
Today's status window is done. Put new updates in tomorrow's thread.
```

3.

```text
*End-of-day status window closed.*
If you missed it, pick it up in tomorrow's thread.
```

4.

```text
*That's a wrap for today's standup.*
No new updates here; keep tomorrow's status in tomorrow's thread.
```

5.

```text
*Standup thread closed for the day.*
Keep the timeline clean and use tomorrow's thread for new updates.
```

## End-of-day escalation

Post this exact text as a reply in the active daily thread when users are still missing. Keep `<@U068KKKNP9R>` as the existing escalation target and upload the selected prepared escalation asset separately in the same thread.

```text
End-of-day check: {MENTIONS} still have no update in the active thread. <@U068KKKNP9R>, please take a look.
```

## Personal standup reminder DM

### Previous Today section was extracted

```text
Quick nudge: your standup update is still missing. Please reply in today's active thread before 13:00.

*Yesterday's plan for Today:*
>{TODAY_PLAN}

<THREAD_LINK|Open today's active standup thread> — deadline is *13:00*
```

### Previous Today section could not be extracted

```text
Quick nudge: your standup update is still missing. I couldn't isolate yesterday's Today section, so here's the full previous post. Please reply in today's active thread before 13:00.

*Full previous post:*
>{FULL_PREVIOUS_POST}

<THREAD_LINK|Open today's active standup thread> — deadline is *13:00*
```

## Related standup alert messages

These are the exact text values sent through the existing alert-channel path.

### Daily thread posted

```text
Today's standup thread is live: <THREAD_LINK|open the active thread>
```

### Missing-report reminder sent

```text
Standup reminder sent to {MISSING_COUNT} missing reporter(s).
```

### All reports received

```text
All standup reports are in. The status thread is complete.
```

### Deployment notification

```text
🚀 Standup bot is back online.
Mode: *Standup collection*.
```

## Approved reaction context

Reaction aliases remain separate from message copy. The approved random-reaction set is:

- `flow-state`
- `monkey-business`
- `investigating`
- `tired-monke`
- `together-4`
- `enough-for-today`
- `stop-nerding`
- `ship`
- `mvp`
- `mvp-2`
- `together-3`
- `together-5`
- `pink-monke`
- `monkey-zen`
- `omg-monkey`

No other reaction alias is included in this proposal.

## Final copy checks

- Every daily opening post contains exactly one banana marker after the team mentions. The opening
  phrases themselves stay clean and do not carry random banana markers.
- The Vacation Tracker fallback contains one clear Monkey Business-flavored leave reference;
  the other leave states stay operational and easy to scan.
- Emoji-inspired variants are restrained and remain understandable without naming the emoji
  aliases in the Slack message.
- Keep the bot identity as `Monkey Scott`; do not introduce a legacy alias.
- The avatar is a monkey version of the existing screaming Michael Scott avatar and is
  handled separately from this copy document.

## Copy decisions preserved

- The deadline remains `13:00`.
- Every standup request keeps the `Yesterday`, `Today`, and `Blockers / Risks` sections.
- Users are asked to reply in the active daily thread.
- Status stays in the main thread; discussions move to subthreads.
- Existing team-group mentions, dynamic missing-user mentions, and `<@U068KKKNP9R>` remain intact.
- The copy keeps the existing cool, edgy Slackbot voice while making the Monkey Business
  theme more visible through selected bananas, proverbs, and emoji-inspired phrases.
