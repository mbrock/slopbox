# Slopbox

Slopbox combines multiple AI image generation models into a web interface. It
handles the generation process, stores the results in a browsable gallery, and
maintains a database of prompts for future use.

The interface shows generation progress in real-time and supports different
image aspect ratios. Images can be viewed individually, in a gallery layout, or
as a slideshow. Users can mark favorites to build personal collections.

```bash
export REPLICATE_API_KEY=your_replicate_api_key
export ANTHROPIC_API_KEY=your_anthropic_api_key
uv run fastapi dev src/slopbox/app.py
```

The application will be available at <http://localhost:8000>.

## License

MIT License
