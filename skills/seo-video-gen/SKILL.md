---
name: seo-video-gen
description: "AI video generation for SEO and social assets: hero background loops, product motion shots, short social reels, and explainer clips. Powered by Google's Gemini Omni model via the Gemini API (reuses the seo-google credential setup). Use when user says \"generate video\", \"create video\", \"gemini omni\", \"video-gen\", \"hero video\", \"background loop\", \"product video\", \"social reel\", \"short\", \"explainer clip\", \"image to video\", \"animate image\", or \"make a video\"."
argument-hint: "[hero|product|reel|explainer|custom] <description> [--image path]"
user-invokable: true
license: MIT
compatibility: "Requires a Google API key with Gemini Omni access (seo-google setup)"
metadata:
  author: AgriciDaniel
  version: "1.0.0"
  category: seo
---

# SEO Video Gen: AI Video Generation with Gemini Omni

Generate short, production-oriented videos for SEO and social use cases using
Google's **Gemini Omni** model (launched May 2026), a multimodal model that turns
text — and optionally a starting image — into video. This skill maps common SEO
needs to sensible aspect ratios, durations, and prompt structure, then calls the
Gemini API through `scripts/gemini_video.py`.

## Architecture Note

This skill goes **directly to Google's Gemini API** — it does not depend on any
third-party video aggregator or extra MCP server. It reuses the same credential
that the `seo-google` skill already uses:
`~/.config/claude-seo/google-api.json` (`api_key`) or the `GOOGLE_API_KEY` env
var. If you have `/seo google` working, video-gen works with the same key,
provided that key has Gemini Omni access.

The skill has two components with distinct roles:
- **SKILL.md** (this file): handles interactive `/seo video-gen` commands.
- **Agent** (`agents/seo-video-gen.md`): audit-only analyst spawned during
  `/seo audit` to flag pages that would benefit from video (and draft prompts).
  It **never auto-generates** — generation costs money and is always explicit.

## Prerequisites

1. A Google API key with access to Gemini Omni video generation. Confirm your
   account/tier at <https://ai.google.dev/gemini-api/docs/omni>.
2. The key configured the same way as `seo-google`:
   ```bash
   # already done if /seo google works:
   cat ~/.config/claude-seo/google-api.json   # { "api_key": "..." }
   # or:
   export GOOGLE_API_KEY="your-key"
   ```
3. Python 3.9+ (the script is standard-library only — no extra pip installs).

> **Model id caveat:** Gemini Omni is a rolling release. The default model id in
> the script is `gemini-omni-flash`. If Google publishes a different id for your
> tier, pass `--model <id>` or set `GEMINI_VIDEO_MODEL`. Check the docs link above
> before assuming the default is current.

## Command Routing

| Invocation | Use case | Defaults |
|---|---|---|
| `/seo video-gen hero <desc>` | Ambient hero/background loop for a landing page | 16:9, 6s |
| `/seo video-gen reel <desc>` | Vertical short for Reels / Shorts / TikTok | 9:16, 8s |
| `/seo video-gen product <desc> --image <path>` | Animate a product still into a motion shot | 1:1, 5s |
| `/seo video-gen explainer <desc>` | Short explainer / process clip | 16:9, 8s |
| `/seo video-gen custom <desc> [flags]` | Full control over every parameter | as given |

## Workflow

When the user runs `/seo video-gen`:

1. **Parse the use case** (hero/reel/product/explainer/custom) and pick the
   default aspect ratio + duration from the table above. The user's explicit
   flags always win.
2. **Engineer the prompt.** Do not pass the raw phrase through. Expand it into a
   structured video prompt — subject, motion, camera, lighting, mood, setting.
   See `references/video-prompt-engineering.md`.
3. **Confirm before spending.** Video generation incurs cost and takes time.
   Show the user the final prompt + parameters and get a go-ahead before calling
   the API (unless they already said "just generate it").
4. **Generate** by invoking the script (never inline API calls):
   ```bash
   python3 scripts/gemini_video.py "<engineered prompt>" \
     --aspect-ratio 9:16 --duration 8 --json
   ```
   Add `--image <path-or-url>` for image-to-video. Add `--mode generate` only if
   your account exposes Omni as a conversational call rather than an async job
   (see `references/omni-models.md`).
5. **Report** the saved path (default `~/Documents/seo_videos/`), model, mode,
   and size. Offer a follow-up: re-roll with a tweaked prompt, or a matching
   aspect-ratio variant for another channel.

## Core Rules

- **Never auto-generate without confirmation** — cost control. The one exception
  is when the user explicitly asks to generate immediately.
- **Always run through `scripts/gemini_video.py`** — it centralizes credential
  handling, SSRF-safe image fetching (`validate_url`), polling, and download.
- **Engineer every prompt** — a bare noun phrase produces weak video. Structure
  it (subject → motion → camera → light → mood).
- **Respect channel specs** — 9:16 for Reels/Shorts, 16:9 for YouTube/hero,
  1:1 for feed. Don't hand a 16:9 clip to a vertical placement.
- **Keep clips short** — 5–8s covers hero loops, reels, and product motion.
  Longer durations cost more and are rarely needed for SEO/social assets.
- **Verify the model id** against the docs when a call 404s on the model — the
  Omni rollout name may have changed.

## Reference Files (load on demand)

- `references/omni-models.md` — model ids, the two API modes (longrunning vs
  generate), parameters, and rollout/verification notes.
- `references/video-prompt-engineering.md` — prompt structure, use-case recipes,
  and SEO/social-specific guidance.

## Relationship to seo-image-gen

`seo-image-gen` produces stills (OG images, hero images, product photos) via
Gemini image models. `seo-video-gen` produces motion from the same Google
account. A common pipeline: generate a hero still with `image-gen`, then feed it
to `video-gen --image` to animate it into a background loop.
