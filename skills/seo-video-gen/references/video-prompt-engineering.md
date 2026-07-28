# Video Prompt Engineering for Gemini Omni

A one-line phrase produces weak, generic video. Expand every request into a
structured prompt before calling `scripts/gemini_video.py`.

## The five-part structure

Compose prompts as: **subject → motion → camera → lighting → mood/setting**.

1. **Subject** — what is on screen (the product, the place, the person/object).
2. **Motion** — what moves and how (slow pan, gentle rotation, drifting clouds,
   steam rising). Video lives or dies on motion; always specify it.
3. **Camera** — shot type and movement (aerial drone push-in, static locked-off,
   slow dolly, orbit).
4. **Lighting** — golden hour, soft studio key, neon, overcast.
5. **Mood / setting** — cinematic, calm, energetic; location and time of day.

Add a `--negative-prompt` for things to exclude (text overlays, watermarks,
distorted hands, jitter).

### Example

> Bare: `"beach video"`
>
> Engineered: `"A quiet tropical beach at sunrise, gentle waves rolling in and
> palm fronds swaying in a light breeze, slow aerial drone push-in over the
> shoreline, warm golden-hour light, calm and cinematic mood"`
> `--negative-prompt "text, watermark, people, harsh shadows"`

## Use-case recipes

### hero (16:9, 6s)
Ambient background loop behind a landing-page headline. Keep motion subtle and
seamless so it can loop. Favor slow camera moves and continuous ambient motion
(water, clouds, light). Avoid hard cuts or fast action.

### reel (9:16, 8s)
Vertical short for Reels/Shorts/TikTok. Front-load a strong first frame — the
first 1s decides the scroll. One clear subject, one clear motion. Leave visual
breathing room at top/bottom for platform UI and captions.

### product (1:1, 5s, `--image`)
Feed a product still with `--image` and describe the motion you want added:
slow rotation on a pedestal, a light sweep across the surface, floating in soft
studio light. Keep the product identity intact — describe motion, not redesign.

### explainer (16:9, 8s)
A short process/concept clip. Describe a simple sequence of visual states rather
than dense narration. Keep one idea per clip.

## SEO & social guidance

- **Match the channel's aspect ratio.** 9:16 vertical for Reels/Shorts, 16:9 for
  YouTube and on-page hero, 1:1 for feed. Never repurpose a 16:9 clip into a
  vertical slot — it crops badly.
- **Design hero loops to loop.** Start and end states should be similar so the
  loop is invisible; avoid a distinctive first/last frame.
- **Keep it short.** 5–8s is plenty for hero, reel, and product motion, and keeps
  cost and render time down.
- **Pair with a still.** Generate a hero image via `/seo image-gen`, then animate
  it with `/seo video-gen product --image <that-file>` for a consistent look.
- **Accessibility & indexing.** Video files aren't crawlable text — always pair
  on-page video with a real caption/transcript and `VideoObject` schema so the
  clip contributes to search visibility rather than just page weight.

## Iteration

If the first result is off, change one variable at a time — usually motion or
camera. Re-roll with the same seed-of-intent prompt and a single adjustment
rather than rewriting the whole prompt, so you can tell what changed.
