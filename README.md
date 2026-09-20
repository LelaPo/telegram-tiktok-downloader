# YouTube to MP3 Telegram Bot

A private, self-hosted Telegram bot built on Python 3.12.10 that extracts high-fidelity MP3s from YouTube URLs, automatically embeds ID3 tags and cover art, and includes an interactive in-chat button editor for fixing metadata.

## Prerequisites

- **Python 3.12.10**
- **FFmpeg**: Required by `yt-dlp` for audio extraction and conversion.
  - Debian/Ubuntu: `sudo apt update && sudo apt install -y ffmpeg`
  - Arch Linux: `sudo pacman -S ffmpeg`

## Installation & Setup

1. **Clone the repository**:
   ```bash
   git clone <repo-url>
   cd yt-audio-bot