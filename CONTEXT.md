# Project context

- Purpose: Create and inspect a small repository starter.
- Repository name: A lowercase slug used only as a folder name and README title.
- Manifest: A JSON map of generated file names to SHA-256 fingerprints.
- Integrity: A matching fingerprint means bytes match the recorded digest. It does not prove trust or secrecy.
- Data choice: No database is created. User projects and files stay in their chosen local destination.
- Reruns: Existing files are preserved. The generator never replaces an existing path.
