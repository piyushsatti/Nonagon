# Moderation SOP

## Quest Nudge Auditing

- Every quest nudge posts a gold "Quest Nudge" embed in the quest channel and includes a link back to the announcement message.
- The bot records each nudge via `send_demo_log`, emitting a guild-scoped entry with the referee mention and quest title.
- Moderators should review the demo log stream during weekly check-ins to confirm nudges stay within the 48h cooldown cadence.
- If a nudge occurs too soon, remind the referee that cooldown enforcement is automatic and note the attempt for follow-up.
