import requests
from typing import Optional, Dict, Any
from .config import DeezerConfig
from .exceptions import DeezerApiException
from logging_config import logger


class DeezerSession:
    def __init__(self, config: DeezerConfig):
        self.config = config
        self.session = self._create_session()
        self.license_token: Optional[str] = None
        self.sound_format: str = "MP3_128"

    def _create_session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update({
            'Pragma': 'no-cache',
            'Origin': 'https://www.deezer.com',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'en-US,en;q=0.9',
            'User-Agent': self.config.user_agent,
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Accept': '*/*',
            'Cache-Control': 'no-cache',
            'X-Requested-With': 'XMLHttpRequest',
            'Connection': 'keep-alive',
            'Referer': 'https://www.deezer.com/login',
            'DNT': '1',
        })
        session.cookies.update({
            'arl': self.config.cookie_arl,
            'comeback': '1'
        })
        return session

    def initialize_session(self):
        """Initialize session with user data and quality settings"""
        user_data = self._get_user_data()
        self.license_token = user_data['license_token']
        self._set_sound_quality(self.config.quality, user_data['web_sound_quality'])

    def _get_user_data(self) -> Dict[str, Any]:
        try:
            response = self.session.get(
                'https://www.deezer.com/ajax/gw-light.php',
                params={
                    'method': 'deezer.getUserData',
                    'input': '3',
                    'api_version': '1.0',
                    'api_token': ''
                }
            )
            response.raise_for_status()
            data = response.json()['results']
            return {
                'license_token': data['USER']['OPTIONS']['license_token'],
                'web_sound_quality': data['USER']['OPTIONS']['web_sound_quality']
            }
        except (requests.exceptions.RequestException, KeyError) as e:
            raise DeezerApiException(f"Failed to get user data: {e}")

    def _set_sound_quality(self, quality_config: str, web_sound_quality: Dict[str, bool]):
        flac_supported = web_sound_quality.get('lossless', False)

        if flac_supported and quality_config == "flac":
            self.sound_format = "FLAC"
        elif flac_supported:
            self.sound_format = "MP3_320"
        else:
            if quality_config == "flac":
                logger.info("WARNING: FLAC quality requested but not supported. Falling back to MP3")
            self.sound_format = "MP3_128"
