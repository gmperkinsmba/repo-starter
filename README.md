# Repo Starter

**First principle:** Keep project setup easy to review and safe to repeat.

Preview and create a local repository with starter files. You can download it as a ZIP or create it in a local folder you choose. The starter includes a README, CONTEXT, MIT license, `.gitignore`, and a SHA-256 file manifest. It does not create a GitHub repository or push code.

## Run

Open `~/Applications/Repo Starter.app` in Finder. The app bundles Python and starts its loopback service when the window opens. No Python install is needed. You do not need a browser tab or server command. Generated projects are saved under `~/.secure-repo-factory/generated/`.

The installed app is unsigned. macOS may ask you to confirm the first launch in Privacy & Security. Quit with Command-Q or close the window. To uninstall, quit the app and move only `~/Applications/Repo Starter.app` to Trash. Generated projects remain in the separate runtime folder.

**Browser alternative**

The source browser mode uses Python 3.10 or newer and the standard library. I did not test browser mode on Linux.

Python 3.10 or newer is required. The app uses only the Python standard library.

```sh
python3 factory.py serve
```

Open <http://127.0.0.1:8312>. The server listens on loopback only. Stop it with Ctrl+C. The web app writes only under `~/.secure-repo-factory/generated/`. It uses private directory permissions. Preview shows each template file before writing it.

**Build from source**

On macOS, use Python 3.12 with the pinned desktop requirements:

```sh
uv venv .desktop-venv --python 3.12
uv pip install --python .desktop-venv/bin/python -r requirements-desktop.lock.txt
.desktop-venv/bin/python build_desktop.py
.desktop-venv/bin/python install_desktop.py
```

The build emits `dist/Repo Starter.app` and refuses to replace an app without its ownership marker. Native builds target macOS; Linux builds are not supported or tested here.

## Use the CLI

Preview a file manifest without writing any files:

```sh
python3 factory.py manifest sample-project
python3 factory.py generate sample-project /tmp/projects --dry-run
```

To generate files and check them later:

```sh
python3 factory.py generate sample-project /tmp/projects
python3 factory.py verify /tmp/projects/sample-project
```

Generation keeps existing files. Matching, edited, and unknown files stay untouched. The manifest records expected file fingerprints. It does not encrypt data or stop deliberate changes. The web app uses a fixed private sandbox. The CLI accepts the folder path you provide.

## Templates and settings

Review the generated files before use. This version has no database and stores no user data. Set your project owner details in the generated files. Update the README, CONTEXT, and license. The web app uses its fixed private sandbox. There are no API tokens or external service settings.

## Tests

```sh
python3 -m unittest -v
```

Tests check dry runs and safe reruns. They scan for fake credentials. They check edited files and ZIP contents. They check request rules and bad slugs. They check that output omits agent settings.

## Limits

The app does not start Git or make remote repos. It cannot change repo access or publish files. The secret scan finds common token patterns. It may miss other secrets. Check generated files and run your own tests before you publish.

## License

Original code uses the MIT License. See `LICENSE`.
