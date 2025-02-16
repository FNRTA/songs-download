from deezer_downloader.client import DeezerClient
from deezer_downloader.config import DeezerConfig
from deezer_downloader.exceptions import DeezerException
import re
from logging_config import logger

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Deezer Downloader')
    parser.add_argument('url', help='Deezer URL (track, album, or playlist)')
    args = parser.parse_args()

    # Configure client
    config = DeezerConfig(
        cookie_arl='',  # Replace with your ARL cookie
    )

    client = DeezerClient(config)
    client.initialize()

    # Extract type and ID from URL
    url_match = re.match(r'https?://(?:www\.)?deezer\.com/(?:\w+/)?(\w+)/(\d+)', args.url)
    if not url_match:
        logger.info("Invalid Deezer URL")
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
            logger.info(f"Unsupported content type: {content_type}")
    except DeezerException as e:
        logger.info(f"Error: {e}")
