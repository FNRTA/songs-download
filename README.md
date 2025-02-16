# Deezer Downloader

A Python library for downloading music from Deezer with support for tracks, albums, and playlists. Features high-quality downloads (MP3/FLAC) with proper metadata handling.

## Features

- Download individual tracks, complete albums, or playlists
- Support for both MP3 and FLAC formats (FLAC requires Deezer Premium)
- Automatic metadata handling
- Progress tracking for downloads
- Concurrent downloads for faster processing
- Error handling with fallback options
- Command-line interface

## Prerequisites

- Python 3.7 or higher
- A Deezer account (Premium account required for FLAC quality)
- Deezer ARL cookie from your account

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/deezer-downloader.git
cd deezer-downloader
```

2. Install required dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

Create a configuration with your Deezer ARL cookie:

```python
from deezer_downloader.config import DeezerConfig

config = DeezerConfig(
    cookie_arl='your_cookie_arl_here',  # Replace with your ARL cookie
    quality='mp3',  # 'mp3' or 'flac'
    download_folder='./downloads'
)
```

To get your ARL cookie:
1. Log in to Deezer in your web browser
2. Open Developer Tools (F12)
3. Go to the Application/Storage tab
4. Find the 'arl' cookie under Cookies > www.deezer.com
5. Copy the cookie value

## Usage

### As a Library

```python
from deezer_downloader.config import DeezerConfig
from deezer_downloader.client import DeezerClient

# Initialize configuration
config = DeezerConfig(
    cookie_arl='your_cookie_arl_here',
    quality='mp3',
    download_folder='./downloads'
)

# Create and initialize client
client = DeezerClient(config)
client.initialize()

# Download a track
client.download_track('925108')

# Download an album
client.download_album('12345')

# Download a playlist
client.download_playlist('3037066082')
```

### Command Line Interface

```bash
# Download a track
python -m deezer_downloader.client "https://www.deezer.com/track/925108" --quality mp3 --output ./downloads

# Download an album
python -m deezer_downloader.client "https://www.deezer.com/album/12345" --quality flac --output ./downloads

# Download a playlist
python -m deezer_downloader.client "https://www.deezer.com/playlist/3037066082" --quality mp3 --output ./downloads
```

## Using the Web Interface

1. Run: python app.py
2. Open a web browser and navigate to `http://localhost:5000`
2. Enter your ARL cookie, Deezer URL
3. Click the "Download" button to start the download process

## app.py File

The `app.py` file is the main application file that runs the web interface. It uses the Flask web framework to create a simple web server that serves the HTML template and handles form submissions.

To use the `app.py` file, simply run it with Python: `python app.py`. This will start the web server and make the web interface available at `http://localhost:5000`.


## Project Structure

```
deezer_downloader/
├── __init__.py
├── config.py         # Configuration handling
├── exceptions.py     # Custom exceptions
├── types.py         # Type definitions
├── crypto.py        # Cryptography utilities
├── session.py       # Session management
└── client.py        # Main client implementation
```

## Error Handling

The library includes several custom exceptions for better error handling:

- `DeezerException`: Base exception class
- `Deezer404Exception`: Resource not found
- `Deezer403Exception`: Authentication required
- `DeezerApiException`: API-related errors

Example error handling:

```python
from deezer_downloader.exceptions import DeezerException

try:
    client.download_track('925108')
except Deezer404Exception:
    print("Track not found")
except Deezer403Exception:
    print("Authentication failed - check your ARL cookie")
except DeezerApiException as e:
    print(f"API error: {e}")
```

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This tool is for personal use only. Please respect Deezer's terms of service and only download content you have the right to access. The developers are not responsible for any misuse of this software.

## Acknowledgments

- Thanks to all contributors who have helped with the development
- Special thanks to the Python community for the excellent libraries that make this possible

## Troubleshooting

### Common Issues

1. **Authentication Errors**
   - Verify your ARL cookie is correct and up to date
   - Make sure you're logged into Deezer in your browser
   - Try clearing browser cookies and getting a new ARL

2. **Download Failures**
   - Check your internet connection
   - Verify the track/album/playlist is available in your region
   - Ensure you have a premium account if trying to download FLAC

3. **Quality Issues**
   - FLAC quality requires a Deezer Premium subscription
   - The library will automatically fall back to MP3 if FLAC is unavailable

For more help, please open an issue on the GitHub repository.
