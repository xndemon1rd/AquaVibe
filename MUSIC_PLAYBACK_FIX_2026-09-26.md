# AquaVibe playback fixes — 2026-09-26

- Re-check auto-end VC participants before stopping playback.
- Use the chat-assigned assistant for the participant check.
- Retry voice-chat creation/play after Telegram call propagation delays.
- Validate local downloaded media with ffprobe before handing it to PyTgCalls.
- Advance both audio and video queues on StreamEnded and log stream/chat lifecycle events.
- Print the actual PyTgCalls/NTgCalls versions during Docker build so stale Railway images are obvious.
