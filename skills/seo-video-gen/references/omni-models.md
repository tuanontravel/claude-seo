# Gemini Omni: Models, Modes & Parameters

Reference for `scripts/gemini_video.py`. Always cross-check the live docs, since
Omni is a rolling release: <https://ai.google.dev/gemini-api/docs/omni>.

## What Gemini Omni is

Gemini Omni is Google's multimodal generation model announced at Google I/O and
rolled out from May 2026. It reasons across text, images, audio, and video and
can generate/edit video from a prompt (and an optional starting image) — a single
multimodal model rather than a chain of separate ones. The first family member is
**Gemini Omni Flash**, available to Google AI Plus/Pro/Ultra subscribers and via
the Gemini API.

## Model id

- Script default: `gemini-omni-flash`.
- Override precedence: `--model <id>` flag > `GEMINI_VIDEO_MODEL` env var > default.
- If a call returns HTTP 404 on the model, the rollout id for your tier differs —
  get the current id from the docs link above and pass it with `--model`.

## The two API modes

Gemini video access is exposed in one of two shapes depending on account/model
tier. The script supports both via `--mode`.

### `--mode longrunning` (default)

Standard async video pattern (same as Veo video jobs):

1. `POST /v1beta/models/{model}:predictLongRunning?key=KEY`
   body: `{"instances":[{"prompt": "...", "image": {...}}], "parameters": {...}}`
2. Response returns an operation: `{"name": "operations/..."}`.
3. Poll `GET /v1beta/{operation}?key=KEY` every `--poll-interval` seconds until
   `"done": true` (or `--max-wait` is hit).
4. Download the resulting MP4 from the file URI in the response (the key is
   appended for the download).

Use this for anything that takes more than a few seconds to render — which is
most video.

### `--mode generate`

Conversational single-call shape:

- `POST /v1beta/models/{model}:generateContent?key=KEY`
  with `generationConfig.responseModalities: ["VIDEO"]` and a `videoConfig`.
- The video comes back as inline base64 bytes in a candidate part.

Use this only if your account exposes Omni video as a direct generate call. If a
`generate` call returns no inline video, switch to `--mode longrunning`.

## Parameters (sent as `parameters` / `videoConfig`)

| Flag | Field | Notes |
|---|---|---|
| `--aspect-ratio` | `aspectRatio` | `16:9`, `9:16`, `1:1`, `4:3`, `3:4`, `21:9` |
| `--duration` | `durationSeconds` | Keep to 5–8s for SEO/social assets |
| `--resolution` | `resolution` | e.g. `720p`, `1080p` |
| `--negative-prompt` | `negativePrompt` | What to keep out of frame |
| `--image` | `instances[].image` / part | Local path or **public** URL (SSRF-validated) |

Field names above match the request bodies the script builds. If Google renames
a field during rollout, update the `params` dict construction in
`scripts/gemini_video.py` — it is intentionally isolated in `main()`.

## Credentials

Reuses the `seo-google` setup — no separate secret:

- `~/.config/claude-seo/google-api.json` → `{"api_key": "..."}`, or
- `GOOGLE_API_KEY` env var.

The key must have Gemini Omni access. A key that works for PageSpeed/CrUX does
not automatically have generative-video access — enable it in Google AI Studio.

## Cost & latency reminders

- Video generation is billed per generation and is far more expensive than image
  or text calls. Never batch-generate speculatively.
- Async jobs can take tens of seconds to minutes. The script polls up to
  `--max-wait` (default 600s) before timing out cleanly.
