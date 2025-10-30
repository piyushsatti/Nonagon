# DM Wizard Interaction Style

We standardize DM-driven workflows around an interactive preview message with persistent controls. The key aspects of the preferred style are:

- **Single preview message.** Wizards open with a DM that includes the latest preview embed and a `discord.ui.View` for navigation.
- **Button-driven edits.** Each field is managed by a button that opens a modal. Modals validate inputs immediately and re-render the shared preview on success.
- **Contextual confirmations.** A dedicated "Create"/"Save" button confirms changes, while a paired cancel button exits gracefully.
- **Consistent feedback.** Errors use the shared `send_ephemeral_message` helper (or the `_flash_message` wrapper in sessions) so responses match the friendly tone across Quest and Character flows.
- **Shared components.** DM sessions use classes from `app.bot.ui.wizards` (`WizardSessionBase`, `PreviewWizardContext`, `PreviewWizardView`, and shared modal/validation helpers) to keep copy, validation, and lifecycle behavior aligned.

When implementing a new DM wizard, construct it around these shared pieces so both quests and characters present the same interaction model.
