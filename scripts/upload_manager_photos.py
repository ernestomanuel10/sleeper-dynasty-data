#!/usr/bin/env python3
"""Upload manager JPEGs from a ZIP to GitHub, using the GitHub Contents API.

Usage:
  GH_TOKEN=github_pat_... python scripts/upload_manager_photos.py dynasty_manager_photos_github.zip
Requires a GitHub token with Contents: Read and write for this repository.
"""
import base64
import json
import os
import sys
import urllib.error
import urllib.request
import zipfile

REPO = "ernestomanuel10/sleeper-dynasty-data"
ROOT = "https://api.github.com/repos/" + REPO + "/contents/"
MANIFEST = "assets/managers/manager_manifest.json"

def request(path, method="GET", payload=None):
    headers = {
        "Authorization": "Bearer " + os.environ["GH_TOKEN"],
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "dynasty-manager-photo-uploader",
    }
    body = json.dumps(payload).encode() if payload is not None else None
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(ROOT + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"GitHub {exc.code} for {path}: {exc.read().decode()[:500]}") from exc

def main(zip_path):
    if not os.environ.get("GH_TOKEN"):
        raise SystemExit("Set GH_TOKEN to a GitHub fine-grained token with Contents: Read and write.")
    info = request(MANIFEST)
    manifest = json.loads(base64.b64decode(info["content"]))
    names = {entry["filename"] for entry in manifest["managers"]}
    with zipfile.ZipFile(zip_path) as archive:
        members = {os.path.basename(n): n for n in archive.namelist() if n.startswith("assets/managers/") and n.lower().endswith(".jpg")}
        if set(members) != names:
            raise SystemExit(f"ZIP filenames mismatch. Missing: {names - set(members)}; extra: {set(members) - names}")
        for entry in manifest["managers"]:
            filename = entry["filename"]
            path = "assets/managers/" + filename
            content = archive.read(members[filename])
            if not content.startswith(b"\xff\xd8\xff"):
                raise SystemExit(f"{filename} is not a JPEG")
            try:
                old = request(path)
                sha = old["sha"]
            except RuntimeError as err:
                if "GitHub 404" not in str(err):
                    raise
                sha = None
            payload = {
                "message": "Upload verified manager photo " + filename,
                "content": base64.b64encode(content).decode("ascii"),
            }
            if sha:
                payload["sha"] = sha
            request(path, "PUT", payload)
            entry["uploaded"] = True
            print("Uploaded", path)
    manifest["status"] = "images_uploaded"
    new_manifest = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    request(MANIFEST, "PUT", {
        "message": "Mark verified manager photos uploaded",
        "content": base64.b64encode(new_manifest.encode()).decode(),
        "sha": info["sha"],
    })
    print("Finished: all 10 images and manifest committed.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/upload_manager_photos.py dynasty_manager_photos_github.zip")
    main(sys.argv[1])
