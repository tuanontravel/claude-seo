#!/usr/bin/env python3
"""Gemini Omni video generation for SEO assets.

Generates short videos with Google's Gemini Omni model (launched May 2026)
via the Gemini Developer API. Powers the ``/seo video-gen`` skill: hero/BGM
loops, product motion shots, social reels, and explainer clips built from a
text prompt and (optionally) a starting image.

Credentials are reused from the existing Claude SEO Google setup
(``google_auth.get_api_key`` -> ``~/.config/claude-seo/google-api.json`` or the
``GOOGLE_API_KEY`` env var), so no new secret store is introduced. The script
uses only the Python standard library so it runs without extra pip installs.

Two API shapes are supported because Gemini video access is exposed differently
depending on the account/model tier:

  --mode longrunning   (default) POST :predictLongRunning, poll the returned
                       operation, then download the finished MP4. This is the
                       standard Gemini video pattern (Veo / Omni video jobs).
  --mode generate      POST :generateContent with a VIDEO response modality and
                       read inline video bytes back. Use this if your account
                       exposes Omni as a conversational generate call.

IMPORTANT — verify the model id and mode against the live docs:
    https://ai.google.dev/gemini-api/docs/omni
The exact Omni model string can change during rollout. Override it with
``--model`` (or the ``GEMINI_VIDEO_MODEL`` env var) without editing this file.

Usage:
    gemini_video.py "drone shot over Ha Long Bay at sunrise, cinematic"
    gemini_video.py "product spins slowly on a pedestal" --image ./shot.jpg
    gemini_video.py "..." --aspect-ratio 9:16 --duration 8 --json
    gemini_video.py "..." --model gemini-omni-flash --mode generate

Exit codes:
    0  video generated and saved
    1  usage / credential / validation error
    2  API or timeout error
"""

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

# Reuse the repo's Google credential + SSRF helpers (same directory).
try:
    from google_auth import get_api_key, validate_url
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from google_auth import get_api_key, validate_url

API_BASE = "https://generativelanguage.googleapis.com/v1beta"
# Default Omni video model. Confirm the current id at the docs URL above; the
# rollout name may differ per account. Overridable via flag or env var.
DEFAULT_MODEL = os.environ.get("GEMINI_VIDEO_MODEL", "gemini-omni-flash")
DEFAULT_ASPECT = "16:9"
DEFAULT_DURATION = 6          # seconds
DEFAULT_RESOLUTION = "720p"
DEFAULT_POLL_INTERVAL = 10    # seconds
DEFAULT_MAX_WAIT = 600        # seconds
OUTPUT_DIR = Path.home() / "Documents" / "seo_videos"

VALID_ASPECTS = {"16:9", "9:16", "1:1", "4:3", "3:4", "21:9"}
IMAGE_MIME = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".png": "image/png", ".webp": "image/webp",
}


def _fail(message, code=1, as_json=False):
    """Emit an error (JSON or plain) and exit."""
    if as_json:
        print(json.dumps({"status": "error", "error": message}, indent=2))
    else:
        print(f"Error: {message}", file=sys.stderr)
    sys.exit(code)


def _post(url, body):
    """POST JSON, return parsed JSON response. Raises urllib errors upward."""
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get(url):
    """GET JSON, return parsed JSON response."""
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _load_image_part(image):
    """Return a Gemini inline_data part for a local path or validated URL."""
    if image.startswith(("http://", "https://")):
        if not validate_url(image):
            _fail(f"Refusing to fetch unsafe image URL: {image}")
        with urllib.request.urlopen(image, timeout=60) as resp:
            raw = resp.read()
        mime = resp.headers.get("Content-Type", "image/jpeg").split(";")[0]
    else:
        path = Path(image).expanduser()
        if not path.is_file():
            _fail(f"Image not found: {image}")
        raw = path.read_bytes()
        mime = IMAGE_MIME.get(path.suffix.lower(), "image/jpeg")
    return {"inline_data": {"mime_type": mime, "data": base64.b64encode(raw).decode()}}


def _save_bytes(raw, out_path):
    """Write video bytes to disk, creating parent dirs."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(raw)
    return out_path


def _extract_download_uri(op_result):
    """Find a video file URI inside a long-running operation response."""
    resp = op_result.get("response", {})
    # Gemini video jobs nest the result under a few possible keys during rollout.
    for key in ("generateVideoResponse", "generatedVideos", "predictions"):
        node = resp.get(key)
        if not node:
            continue
        items = node if isinstance(node, list) else node.get("generatedSamples", node)
        if isinstance(items, dict):
            items = [items]
        for item in items or []:
            video = item.get("video") or item.get("_self") or item
            uri = (video.get("uri") if isinstance(video, dict) else None) \
                or item.get("videoUri")
            if uri:
                return uri
    return None


def generate_longrunning(model, prompt, api_key, image_part, params, out_path,
                         poll_interval, max_wait):
    """Async video job: submit -> poll operation -> download MP4."""
    instance = {"prompt": prompt}
    if image_part:
        instance["image"] = image_part["inline_data"]
    body = {"instances": [instance], "parameters": params}

    submit_url = f"{API_BASE}/models/{model}:predictLongRunning?key={api_key}"
    op = _post(submit_url, body)
    op_name = op.get("name")
    if not op_name:
        raise RuntimeError(f"No operation name returned: {json.dumps(op)[:400]}")

    poll_url = f"{API_BASE}/{op_name}?key={api_key}"
    waited = 0
    while waited < max_wait:
        time.sleep(poll_interval)
        waited += poll_interval
        status = _get(poll_url)
        if status.get("error"):
            raise RuntimeError(f"Operation failed: {json.dumps(status['error'])}")
        if status.get("done"):
            uri = _extract_download_uri(status)
            if not uri:
                raise RuntimeError(
                    "Operation done but no video URI found. Raw response:\n"
                    + json.dumps(status.get("response", {}), indent=2)[:800]
                )
            dl = uri if "key=" in uri else f"{uri}{'&' if '?' in uri else '?'}key={api_key}"
            with urllib.request.urlopen(dl, timeout=180) as resp:
                _save_bytes(resp.read(), out_path)
            return {"operation": op_name, "waited_seconds": waited, "source_uri": uri}
    raise TimeoutError(f"Timed out after {max_wait}s (operation {op_name} still running)")


def generate_inline(model, prompt, api_key, image_part, params, out_path):
    """Conversational video: generateContent with a VIDEO response modality."""
    parts = [{"text": prompt}]
    if image_part:
        parts.append(image_part)
    body = {
        "contents": [{"parts": parts}],
        "generationConfig": {"responseModalities": ["VIDEO"], "videoConfig": params},
    }
    url = f"{API_BASE}/models/{model}:generateContent?key={api_key}"
    result = _post(url, body)
    for cand in result.get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            blob = part.get("inline_data") or part.get("inlineData")
            if blob and str(blob.get("mime_type", blob.get("mimeType", ""))).startswith("video"):
                _save_bytes(base64.b64decode(blob["data"]), out_path)
                return {"finish_reason": cand.get("finishReason")}
    raise RuntimeError(
        "No inline video returned. The model may require --mode longrunning. "
        "Raw:\n" + json.dumps(result, indent=2)[:800]
    )


def main():
    parser = argparse.ArgumentParser(
        description="Generate SEO videos with Google's Gemini Omni model.")
    parser.add_argument("prompt", nargs="?", help="Text prompt describing the video")
    parser.add_argument("--prompt", dest="prompt_flag", help="Alternative to positional prompt")
    parser.add_argument("--image", help="Starting image (local path or public URL) for image-to-video")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Model id (default: {DEFAULT_MODEL})")
    parser.add_argument("--mode", choices=("longrunning", "generate"), default="longrunning",
                        help="API shape: longrunning (default) or generate")
    parser.add_argument("--aspect-ratio", default=DEFAULT_ASPECT, choices=sorted(VALID_ASPECTS))
    parser.add_argument("--duration", type=int, default=DEFAULT_DURATION, help="Length in seconds")
    parser.add_argument("--resolution", default=DEFAULT_RESOLUTION, help="e.g. 720p, 1080p")
    parser.add_argument("--negative-prompt", help="What to avoid in the video")
    parser.add_argument("--api-key", help="Google API key (else config/env is used)")
    parser.add_argument("--output", help="Output MP4 path (default: ~/Documents/seo_videos/)")
    parser.add_argument("--poll-interval", type=int, default=DEFAULT_POLL_INTERVAL)
    parser.add_argument("--max-wait", type=int, default=DEFAULT_MAX_WAIT)
    parser.add_argument("--json", action="store_true", help="Emit JSON result")
    args = parser.parse_args()

    prompt = args.prompt_flag or args.prompt
    if not prompt:
        _fail("A prompt is required.", as_json=args.json)

    api_key = args.api_key or get_api_key()
    if not api_key:
        _fail("No Google API key found. Set it in ~/.config/claude-seo/google-api.json "
              "or the GOOGLE_API_KEY env var (needs Gemini Omni access).", as_json=args.json)

    image_part = _load_image_part(args.image) if args.image else None

    if args.output:
        out_path = Path(args.output).expanduser()
    else:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = OUTPUT_DIR / f"seo_video_{stamp}.mp4"

    params = {
        "aspectRatio": args.aspect_ratio,
        "durationSeconds": args.duration,
        "resolution": args.resolution,
    }
    if args.negative_prompt:
        params["negativePrompt"] = args.negative_prompt

    try:
        if args.mode == "longrunning":
            meta = generate_longrunning(args.model, prompt, api_key, image_part,
                                        params, out_path, args.poll_interval, args.max_wait)
        else:
            meta = generate_inline(args.model, prompt, api_key, image_part, params, out_path)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:600]
        _fail(f"Gemini API HTTP {e.code}: {detail}", code=2, as_json=args.json)
    except (urllib.error.URLError, TimeoutError, RuntimeError) as e:
        _fail(str(e), code=2, as_json=args.json)

    result = {
        "status": "success",
        "output": str(out_path),
        "size_bytes": out_path.stat().st_size if out_path.exists() else 0,
        "model": args.model,
        "mode": args.mode,
        "prompt": prompt,
        "aspect_ratio": args.aspect_ratio,
        "duration_seconds": args.duration,
        **meta,
    }
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"✓ Video saved: {out_path}")
        print(f"  Model: {args.model} ({args.mode})  |  {args.aspect_ratio}, {args.duration}s")
        print(f"  Size: {result['size_bytes'] / 1_000_000:.1f} MB")


if __name__ == "__main__":
    main()
