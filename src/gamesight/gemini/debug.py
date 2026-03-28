"""Automatic LLM interaction debug logging.

Enable: set DEBUG_LLM=true in environment or .env file.
Each process run creates one timestamped directory under .tmp/debug/.
Each Gemini API call is saved as a numbered readable markdown file.
"""

import itertools
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel


_enabled: bool | None = None
_session_dir: Path | None = None
_counter = itertools.count(1)


def is_enabled() -> bool:
    global _enabled
    if _enabled is None:
        _enabled = os.environ.get("DEBUG_LLM", "").lower() in ("1", "true", "yes")
    return _enabled


def _get_session_dir() -> Path:
    global _session_dir
    if _session_dir is None:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        _session_dir = Path(".tmp/debug") / timestamp
        _session_dir.mkdir(parents=True, exist_ok=True)
    return _session_dir


_SCHEMA_LABELS: dict[str, str] = {
    "TimelineChunkResult": "timeline",
    "FrictionChunkAnalysis": "friction",
    "ClarityChunkAnalysis": "clarity",
    "DelightChunkAnalysis": "delight",
    "QualityChunkAnalysis": "quality",
}


def _infer_label(response_schema: type | None, system_instruction: str | None) -> str:
    if response_schema is not None:
        return _SCHEMA_LABELS.get(response_schema.__name__, response_schema.__name__.lower())
    if system_instruction and "timeline" in system_instruction.lower():
        return "timeline"
    return "text"


def _serialize_part(part: Any) -> str:
    text = getattr(part, "text", None)
    if text:
        return text

    file_data = getattr(part, "file_data", None)
    video_metadata = getattr(part, "video_metadata", None)

    if file_data is not None:
        file_uri = getattr(file_data, "file_uri", None) or ""
        mime_type = getattr(file_data, "mime_type", None) or ""
        meta_parts: list[str] = []
        if video_metadata:
            for attr, label in [("fps", "fps"), ("start_offset", "start"), ("end_offset", "end")]:
                val = getattr(video_metadata, attr, None)
                if val is not None:
                    meta_parts.append(f"{label}={val}")
        meta_str = " " + " ".join(meta_parts) if meta_parts else ""
        if "youtube.com" in file_uri or "youtu.be" in file_uri:
            return f"[VIDEO: {file_uri}{meta_str}]"
        if mime_type.startswith(("video/", "image/", "audio/")):
            return f"[FILE: {file_uri} {mime_type}{meta_str}]"
        return f"[FILE: {file_uri} {mime_type}{meta_str}]"

    inline_data = getattr(part, "inline_data", None)
    if inline_data is not None:
        mime_type = getattr(inline_data, "mime_type", None) or "unknown"
        return f"[INLINE_DATA: {mime_type}]"

    return "[UNKNOWN PART]"


def _serialize_contents(contents: Any) -> str:
    if contents is None:
        return "(empty)"
    if isinstance(contents, str):
        return contents
    if isinstance(contents, list):
        sections: list[str] = []
        for item in contents:
            role = getattr(item, "role", None)
            parts = getattr(item, "parts", None)
            if role and parts:
                parts_text = "\n".join(_serialize_part(p) for p in parts)
                sections.append(f"### {role.upper()}\n\n{parts_text}")
            else:
                sections.append(str(item))
        return "\n\n".join(sections)
    # Single Content object
    role = getattr(contents, "role", None)
    parts = getattr(contents, "parts", None)
    if role and parts:
        parts_text = "\n".join(_serialize_part(p) for p in parts)
        return f"### {role.upper()}\n\n{parts_text}"
    return str(contents)


def _serialize_response(response: Any) -> str:
    sections: list[str] = []

    candidates = getattr(response, "candidates", None) or []
    if candidates:
        finish_reason = getattr(candidates[0], "finish_reason", None)
        if finish_reason:
            name = getattr(finish_reason, "name", None) or str(finish_reason)
            sections.append(f"**Finish reason**: {name}")

    usage = getattr(response, "usage_metadata", None)
    if usage:
        token_parts: list[str] = []
        for attr, label in [
            ("prompt_token_count", "prompt"),
            ("candidates_token_count", "response"),
            ("total_token_count", "total"),
            ("cached_content_token_count", "cached"),
        ]:
            val = getattr(usage, attr, None)
            if val:
                token_parts.append(f"{label}={val}")
        if token_parts:
            sections.append(f"**Tokens**: {', '.join(token_parts)}")

    parsed = getattr(response, "parsed", None)
    if parsed is not None:
        if isinstance(parsed, BaseModel):
            dump = parsed.model_dump(mode="json")
            sections.append(f"**Parsed output**:\n```json\n{json.dumps(dump, indent=2, default=str)}\n```")
        else:
            sections.append(f"**Parsed output**:\n```\n{parsed}\n```")

    text = getattr(response, "text", None)
    if text:
        sections.append(f"**Raw text**:\n\n{text}")

    return "\n\n".join(sections) if sections else "(empty response)"


def log_interaction(
    *,
    contents: Any,
    response: Any,
    model: str,
    system_instruction: str | None,
    cached_content: str | None,
    media_resolution: Any,
    thinking_level: str,
    response_schema: type | None,
    error: Exception | None = None,
) -> None:
    if not is_enabled():
        return

    seq = next(_counter)
    now = datetime.now()
    label = _infer_label(response_schema, system_instruction)
    filename = f"{seq:03d}_{now.strftime('%H-%M-%S')}_{label}.md"
    filepath = _get_session_dir() / filename

    config_lines = [f"- **Model**: `{model}`", f"- **Thinking level**: {thinking_level}"]
    if response_schema:
        config_lines.append(f"- **Response schema**: `{response_schema.__name__}`")
    if cached_content:
        config_lines.append(f"- **Cached content**: `{cached_content}`")
    if media_resolution:
        config_lines.append(f"- **Media resolution**: `{media_resolution}`")

    lines = [
        f"# LLM Interaction #{seq}",
        f"**Time**: {now.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Config",
        "",
        *config_lines,
        "",
    ]

    if system_instruction:
        lines.extend(["## System Instruction", "", system_instruction, ""])

    lines.extend(["## Contents (Input)", "", _serialize_contents(contents), ""])

    if error:
        lines.extend(["## Error", "", f"```\n{type(error).__name__}: {error}\n```", ""])

    if response is not None:
        lines.extend(["## Response", "", _serialize_response(response), ""])

    filepath.write_text("\n".join(lines), encoding="utf-8")


__all__ = ["is_enabled", "log_interaction"]
