# Security

Repo Starter checks project names and output paths, preserves existing files, and writes into an owner-only folder. SHA-256 manifests let you compare generated files later; they do not encrypt them. File reads and manifest sizes are capped, files are hashed in chunks, and symlinks or file changes during a read are rejected. Generated files are not run by the app. The local server checks Host and Origin, requires a request token, and limits request size.

Keep generated files private if they contain private project details. Generated output files are plaintext in the selected folder. Use your Mac’s disk encryption to protect saved files. The native app has an ad-hoc code signature. This lets the installer check whether its files changed. It does not prove who made the app. The build is not notarized.

Report security issues through [GitHub private vulnerability reporting](https://github.com/gmperkinsmba/repo-starter/security/advisories/new).
