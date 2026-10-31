# Secure Repo Factory

**First principle:** Keep project setup easy to review and safe to repeat.

Secure Repo Factory previews a generic repository starter. You can download it as a ZIP or create it in a local folder you choose. The starter includes a README, CONTEXT, MIT license, `.gitignore`, and a SHA-256 file manifest. It does not create a GitHub repository or push code.

## Run the web app

Python 3.10 or newer is required. The app uses only the Python standard library.

```sh
python3 factory.py serve
```

Open <http://127.0.0.1:8312>. The server listens on loopback only. Stop it with Ctrl+C. The web app writes only under `~/.secure-repo-factory/generated/`. It uses private directory permissions. Preview shows each template file before writing it.

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

Tests cover dry runs and safe reruns. They scan for fake credentials. They check edited-file verification, ZIP contents, request boundaries, bad slugs, and omitted agent configuration.

## Limits

The app does not initialize Git or create remote repositories. It cannot change their visibility or publish files. The secret scan catches common token patterns, but may miss other secrets. Review generated files and run your own checks before publishing.

## License

Original code uses the MIT License. See `LICENSE`.
