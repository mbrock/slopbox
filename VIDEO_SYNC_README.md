# Video Sync Tool

A browser-based video-audio synchronization tool with real-time waveform visualization and server-side export capabilities.

## Features

- **Real-time Waveform Visualization**: View audio waveforms for both video and replacement audio
- **Interactive Sync Controls**: Adjust audio offset with millisecond precision
- **Crossfader**: Mix between original video audio and replacement audio
- **Live Preview**: Real-time audio synchronization while watching the video
- **Dual Export Options**:
  - Browser-based export using WebCodecs API
  - Server-side export using FFmpeg for high quality
- **Progress Tracking**: Real-time progress monitoring for server exports
- **Optimized Encoding**: Smart video stream copying for faster processing

## Running the Video Sync Tool

### Standalone Mode (Video Sync Only)

Run just the video sync tool on port 8000:

```bash
python run_videosync.py
```

Or with custom options:

```bash
python run_videosync.py --host 0.0.0.0 --port 8080 --reload
```

Access at: http://localhost:8000

### As Part of Main Slopbox App

The video sync tool is also available as part of the main slopbox application at `/video-sync`.

## Usage

1. **Upload Files**: Upload your video file and the replacement audio file
2. **Sync Audio**: Use the offset controls to align the audio with the video
3. **Preview**: Use the crossfader to blend between original and replacement audio
4. **Export**: Choose browser or server export for the synchronized video

## Server Requirements

For server-side export, FFmpeg must be installed and available in the system PATH:

```bash
# macOS (via Homebrew)
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# Windows (via Chocolatey)
choco install ffmpeg
```

## API Endpoints

When running standalone, the video sync tool provides these endpoints:

- `GET /` - Main video sync interface
- `POST /export-video-server` - Start server-side export
- `GET /export-progress/{job_id}` - Monitor export progress (SSE)
- `GET /export-download/{job_id}` - Download completed export

## Development

For development with auto-reload:

```bash
python run_videosync.py --reload
```

The tool uses FastAPI with TagFlow for HTML rendering and includes comprehensive debug logging for troubleshooting export issues.