# Slopbox

Slopbox combines multiple AI image generation models into a web interface with video-audio synchronization capabilities. It handles AI image generation, stores results in a browsable gallery, maintains a database of prompts, and provides professional video sync tools.

## Features

### AI Image Generation
- Multiple AI models (Flux, Recraft) with real-time progress tracking
- Gallery with favorites, slideshows, and prompt management
- Batch generation and Claude-powered prompt modification

### Video Sync Tool
- Browser-based video-audio synchronization with waveform visualization
- Real-time crossfading between original and replacement audio
- Dual export: browser-based (WebCodecs) and server-side (FFmpeg)
- Optimized encoding with smart video stream copying

## Quick Start

### Easiest Way (No Installation)

Run directly with uvx:

```bash
# Full slopbox application (recommended)
uvx slopbox

# Video sync tool only
uvx videosync --from slopbox

# With custom options
uvx slopbox --port 8080 --host 0.0.0.0
uvx videosync --from slopbox --port 3000
```

### Installation

Install from PyPI with any Python package manager:

```bash
# With uv (recommended)
uv add slopbox

# With pip
pip install slopbox

# With pipx (for CLI tools)
pipx install slopbox
```

### Running the Applications

After installation, you can run either application with simple commands:

```bash
# Video sync tool only
videosync                        # Default: localhost:8000
videosync --port 3000            # Custom port
videosync --host 0.0.0.0         # Accessible from network
videosync --no-reload            # Disable auto-reload

# Full slopbox application  
slopbox                          # Default: localhost:8000
slopbox --port 8080 --host 0.0.0.0  # Custom host and port

# Get help
videosync --help
slopbox --help
```

### Development

For development with hot reloading:

```bash
# Clone and install in development mode
git clone https://github.com/mbrock/slopbox
cd slopbox
uv sync

# Start development servers
make videosync    # or ./dev videosync
make slopbox      # or ./dev slopbox --port 8080
```

### Environment Setup

```bash
# Set up API keys for image generation (optional for video sync)
export REPLICATE_API_KEY=your_replicate_api_key
export ANTHROPIC_API_KEY=your_anthropic_api_key
```

### Video Sync Requirements

For server-side video export, install FFmpeg:

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian  
sudo apt install ffmpeg
```

## Development Commands

```bash
make help          # Show all available commands
make videosync     # Start video sync tool
make slopbox       # Start full application
make install       # Install dependencies
make lint          # Run code linting
make format        # Format code
make test          # Run tests
make clean         # Clean temporary files
```

## Project Structure

- `src/slopbox/` - Main application code
- `src/slopbox/videosync.py` - Video sync router and functionality
- `videosync_app.py` - Standalone video sync application
- `dev.py` - Development server launcher
- `static/` - Client-side assets (CSS, JS)

The video sync tool can run standalone or as part of the main application at `/video-sync`.

## License

MIT License
