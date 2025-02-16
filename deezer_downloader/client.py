import os
import re
import json
import requests
from typing import List, Dict, Any, Optional, Tuple
from html.parser import HTMLParser
from .sessions import DeezerSession
from .config import DeezerConfig
from .crypto import DeezerCrypto
from .exceptions import DeezerException, DeezerApiException, Deezer403Exception, Deezer404Exception
from progress_tracker import ProgressTracker
from logging_config import logger


class ScriptExtractor(HTMLParser):
    """Extract <script> tag contents from HTML page"""

    def __init__(self):
        super().__init__()
        self.scripts = []
        self.current_tag = None

    def handle_starttag(self, tag, attrs):
        self.current_tag = tag.lower()

    def handle_data(self, data):
        if self.current_tag == "script":
            self.scripts.append(data)

    def handle_endtag(self, tag):
        self.current_tag = None


class DeezerClient:
    def __init__(self, config: DeezerConfig):
        self.config = config
        self.session = DeezerSession(config)
        self.progress_tracker = ProgressTracker()  # Reference to the global progress

    def initialize(self):
        """Initialize the client session"""
        self.session.initialize_session()

    def download_track(self, track_id: str, output_path: Optional[str] = None) -> str:
        """
        Download a single track by ID

        Args:
            track_id: Deezer track ID
            output_path: Optional custom output path

        Returns:
            Path to downloaded file
        """
        # Update progress
        self.progress_tracker.update(
            current=self.progress_tracker.get_progress()['current'] + 1,
            total=self.progress_tracker.get_progress()['total']
        )
        track_info = self._get_track_info(track_id)

        if not output_path:
            # Clean filename of invalid characters
            clean_title = re.sub(r'[<>:"/\\|?*]', '', track_info['SNG_TITLE'])
            filename = f"{clean_title}.{self._get_file_extension()}"
            output_path = os.path.join(self.config.download_folder, filename)

        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        self._download_and_decrypt_track(track_info, output_path)
        return output_path

    def download_playlist(self, playlist_id: str) -> List[str]:
        """
        Download all tracks in a playlist

        Args:
            playlist_id: Deezer playlist ID

        Returns:
            List of paths to downloaded files
        """
        playlist_name, tracks = self._get_playlist_tracks(playlist_id)

        self.progress_tracker.update(current=0, total=len(tracks), finished=False)

        downloaded_files = []

        logger.info(f"Downloading playlist '{playlist_name}' ({len(tracks)} tracks)")

        for i, track in enumerate(tracks, 1):
            try:
                logger.info(f"[{i}/{len(tracks)}] Downloading: {track['SNG_TITLE']}")
                path = self.download_track(str(track['SNG_ID']))
                self.progress_tracker.update(current=i, total=len(tracks))
                downloaded_files.append(path)
            except DeezerException as e:
                logger.info(f"Failed to download track {track['SNG_TITLE']}: {e}")
        self.progress_tracker.update(current=len(tracks), total=len(tracks), finished=True)
        return downloaded_files

    def download_album(self, album_id: str) -> List[str]:
        """
        Download all tracks in an album

        Args:
            album_id: Deezer album ID

        Returns:
            List of paths to downloaded files
        """
        tracks = self._get_album_tracks(album_id)
        self.progress_tracker.update(current=0, total=len(tracks), finished=False)

        downloaded_files = []

        logger.info(f"Downloading album '{tracks[0]['ALB_TITLE']}' ({len(tracks)} tracks)")

        for i, track in enumerate(tracks, 1):
            try:
                logger.info(f"[{i}/{len(tracks)}] Downloading: {track['SNG_TITLE']}")
                path = self.download_track(str(track['SNG_ID']))
                self.progress_tracker.update(current=i, total=len(tracks))
                downloaded_files.append(path)
            except DeezerException as e:
                logger.info(f"Failed to download track {track['SNG_TITLE']}: {e}")
        self.progress_tracker.update(current=len(tracks), total=len(tracks), finished=True)  # Mark as finished
        return downloaded_files

    def _get_file_extension(self) -> str:
        return "flac" if self.session.sound_format == "FLAC" else "mp3"

    def _get_track_info(self, track_id: str) -> Dict[str, Any]:
        """Get track metadata from Deezer"""
        response = self.session.session.get(f"https://www.deezer.com/us/track/{track_id}")

        if response.status_code == 404:
            raise Deezer404Exception(f"Track {track_id} not found")
        if "MD5_ORIGIN" not in response.text:
            raise Deezer403Exception("Authentication required")

        parser = ScriptExtractor()
        parser.feed(response.text)
        parser.close()

        for script in parser.scripts:
            regex = re.search(r'{"DATA":.*', script)
            if regex:
                data = json.loads(regex.group())
                if data['DATA']['__TYPE__'] == 'song':
                    return data['DATA']

        raise DeezerApiException("Could not find track information")

    def _download_and_decrypt_track(self, track_info: Dict[str, Any], output_path: str):
        """Download and decrypt a track"""
        try:
            url = self._get_track_url(track_info['TRACK_TOKEN'])
        except Exception as e:
            if "FALLBACK" in track_info:
                logger.info(f"Track not available, trying fallback version...")
                track_info = track_info["FALLBACK"]
                url = self._get_track_url(track_info['TRACK_TOKEN'])
            else:
                raise DeezerApiException(f"Track not available: {e}")

        key = DeezerCrypto.calc_blowfish_key(track_info['SNG_ID'])

        try:
            with self.session.session.get(url, stream=True) as response:
                response.raise_for_status()
                with open(output_path, "wb") as output_file:
                    DeezerCrypto.decrypt_file(response, key, output_file)
            logger.info(f"Successfully downloaded: {output_path}")
        except Exception as e:
            raise DeezerApiException(f"Download failed: {e}")

    def _get_track_url(self, track_token: str) -> str:
        """Get the download URL for a track"""
        try:
            response = requests.post(
                "https://media.deezer.com/v1/get_url",
                json={
                    'license_token': self.session.license_token,
                    'media': [{
                        'type': "FULL",
                        "formats": [
                            {"cipher": "BF_CBC_STRIPE", "format": self.session.sound_format}
                        ]
                    }],
                    'track_tokens': [track_token]
                },
                headers={
                    'User-Agent': self.config.user_agent
                }
            )
            response.raise_for_status()
            data = response.json()

            if not data.get('data') or 'errors' in data['data'][0]:
                raise DeezerApiException(
                    f"Failed to get download URL: {data['data'][0]['errors'][0]['message']}"
                )

            return data['data'][0]['media'][0]['sources'][0]['url']
        except Exception as e:
            raise DeezerApiException(f"Failed to get track URL: {e}")

    def _get_playlist_tracks(self, playlist_id: str) -> Tuple[str, List[Dict[str, Any]]]:
        """Get all tracks in a playlist"""
        # Extract numeric ID from URL if needed
        playlist_id = re.search(r'\d+', playlist_id).group(0)

        # Get CSRF token
        response = self.session.session.post(
            "https://www.deezer.com/ajax/gw-light.php",
            params={
                'method': 'deezer.getUserData',
                'input': '3',
                'api_version': '1.0',
                'api_token': ''
            }
        )
        csrf_token = response.json()['results']['checkForm']

        # Get playlist data
        response = self.session.session.post(
            "https://www.deezer.com/ajax/gw-light.php",
            params={
                'method': 'deezer.pagePlaylist',
                'input': '3',
                'api_version': '1.0',
                'api_token': csrf_token
            },
            json={
                'playlist_id': int(playlist_id),
                'start': 0,
                'tab': 0,
                'header': True,
                'lang': 'en',
                'nb': 500
            }
        )

        data = response.json()
        if data.get('error'):
            raise DeezerApiException(f"Failed to get playlist: {data['error']}")

        return data['results']['DATA']['TITLE'], data['results']['SONGS']['data']

    def _get_album_tracks(self, album_id: str) -> List[Dict[str, Any]]:
        """Get all tracks in an album"""
        response = self.session.session.get(f"https://www.deezer.com/us/album/{album_id}")

        if response.status_code == 404:
            raise Deezer404Exception(f"Album {album_id} not found")
        if "MD5_ORIGIN" not in response.text:
            raise Deezer403Exception("Authentication required")

        parser = ScriptExtractor()
        parser.feed(response.text)
        parser.close()

        for script in parser.scripts:
            regex = re.search(r'{"DATA":.*', script)
            if regex:
                data = json.loads(regex.group())
                if data['DATA']['__TYPE__'] == 'album':
                    return data['SONGS']['data']

        raise DeezerApiException("Could not find album information")
