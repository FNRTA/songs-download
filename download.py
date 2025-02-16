from deezer_downloader.client import DeezerClient
from deezer_downloader.config import DeezerConfig
from deezer_downloader.exceptions import DeezerException
import re

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Deezer Downloader')
    parser.add_argument('url', help='Deezer URL (track, album, or playlist)')
    parser.add_argument('--quality', choices=['mp3', 'flac'], default='mp3', help='Audio quality (default: mp3)')
    parser.add_argument('--output', '-o', help='Output directory (default: ./downloads)')
    args = parser.parse_args()

    # Configure client
    config = DeezerConfig(
        cookie_arl='3c4b24b215afa45bee789ef23f691789f589a84f844f9dbbd6e115080a2806831389a14ad3dfed6e58b6f77da3715af588e9caa0a42017c629acca110d2abcd5bf43c1b69a7c8b56b4be6c721b705f9f522e847d44dc0c5c09261ecde5988316',  # Replace with your ARL cookie
    )

    client = DeezerClient(config)
    client.initialize()

    # Extract type and ID from URL
    url_match = re.match(r'https?://(?:www\.)?deezer\.com/(?:\w+/)?(\w+)/(\d+)', args.url)
    if not url_match:
        print("Invalid Deezer URL")
        exit(1)

    content_type, content_id = url_match.groups()

    try:
        if content_type == 'track':
            client.download_track(content_id)
        elif content_type == 'album':
            client.download_album(content_id)
        elif content_type == 'playlist':
            client.download_playlist(content_id)
        else:
            print(f"Unsupported content type: {content_type}")
    except DeezerException as e:
        print(f"Error: {e}")