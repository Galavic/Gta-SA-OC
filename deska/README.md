# Deska panels

Panels for [Deska](https://deska.dev) that live beside the GTA San Andreas web port. They are desk companions, not part of the game runtime.

| Panel | What it is |
| --- | --- |
| [`san-andreas-web`](san-andreas-web) | Opens the public launcher, shows a dated snapshot of verified milestones, and keeps a personal test log in Deska storage. |

## Load a panel

In Deska, open the Panel Library (`Ctrl+Shift+E` outside macOS), choose **Community → Build a panel → Load a folder**, and select the panel folder (the one containing `panel.json`).

## Rules

- Panels reuse Deska's theme tokens for every color, so they follow the app's light/dark mode and accent.
- Panels declare only the permissions and network hosts they use. `san-andreas-web` asks for `open-url` and declares no network hosts.
- No game assets, credentials or personal paths are included in a panel.
- A panel is a UI companion. Its status snapshot does not verify or change gameplay.

The structure follows the example community panels from [0xPasho/deska-panels-examples](https://github.com/0xPasho/deska-panels-examples) (MIT).
