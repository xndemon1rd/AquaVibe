# Nebula AI integration

AquaVibe now gates AI image/video generation behind VIP/VIP Pro and protects the free backend from overload:

- VIP/VIP Pro: 3 images/day + 2 videos/day
- Owner (`OWNER_ID`): unlimited and does not consume the quota
- `/cimage` and `/getdraw`: image generation
- `/cvideo`: video generation
- `/anime` and `/asearch`: VIP/VIP Pro only

## Provider bridge

Nebula's public page says its free studio uses Stable Horde and the anonymous Horde key `0000000000`. AquaVibe therefore uses that same free image backend directly. Video uses the public Wan 2.2 Hugging Face Space used by the open-source NiftyVid project, through `gradio_client`; no provider API key is required.

Optional Railway variables:

```text
NEBULA_HORDE_BASE=https://stablehorde.net/api/v2
NEBULA_HORDE_KEY=0000000000
NEBULA_IMAGE_MODEL=AlbedoBase XL
NEBULA_VIDEO_SPACE=cbensimon/wan2-2-fp8da-aoti-preview2
NEBULA_IMAGE_TIMEOUT=180
NEBULA_VIDEO_MAX_SECONDS=4.5
NEBULA_VIDEO_STEPS=20
```

The defaults work without adding a Nebula API key. The anonymous Horde backend can queue when volunteer capacity is busy; this is expected for the free public infrastructure.
