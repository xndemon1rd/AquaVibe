# 2026-10-01 - Gemini-only image & video creation

- Removed DeepAI (`DEEP_API`) everywhere: `/cimage`, `/getdraw`, `/cvideo`, `/upscale`.
- Removed OpenAI from image generation (chat fallback via OpenAI is unchanged).
- `/cimage` and `/getdraw` -> Gemini image model (`GEMINI_IMAGE_MODEL`, default `gemini-3.1-flash-image`).
- `/cvideo` -> Gemini Veo (`GEMINI_VIDEO_MODEL`, default `veo-3.1-generate-preview`), async job + polling.
- `/upscale` now uses a local 2x Lanczos upscale only (Gemini has no upscaler endpoint).
- Only `GEMINI_API_KEY` is needed.
