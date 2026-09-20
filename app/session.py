#!/usr/bin/env python3
"""session.py — save/load the JSON session file (spec section 7).

Stores paths, model/settings versions, detected events, user edits and
export history. Source audio is referenced, never embedded. On load, missing
audio files are reported so the UI can prompt to relink.
"""
import json
import os
from datetime import datetime, timezone

from app.models import Project
from app import pipeline


def save_session(project, path, models_info=None):
    data = project.to_dict()
    data["app"] = "stem-to-midi workspace"
    data["saved_at"] = datetime.now(timezone.utc).isoformat()
    data["models"] = models_info or pipeline.model_versions()
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, path)
    return path


def load_session(path):
    """Returns (project, missing_files). missing_files: list of wav paths."""
    with open(path) as f:
        data = json.load(f)
    project = Project.from_dict(data)
    missing = []
    if project.source_path and not os.path.isfile(project.source_path):
        missing.append(project.source_path)
    for stem in project.stems:
        if stem.wav_path and not os.path.isfile(stem.wav_path) \
                and stem.wav_path not in missing:
            missing.append(stem.wav_path)
    return project, missing


def relink(project, old_path, new_path):
    """Point a missing file at its new location. Returns True if applied."""
    changed = False
    if project.source_path == old_path:
        project.source_path = new_path
        changed = True
    for stem in project.stems:
        if stem.wav_path == old_path:
            stem.wav_path = new_path
            stem._audio = None  # drop cached audio
            changed = True
    return changed
