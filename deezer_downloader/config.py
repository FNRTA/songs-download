from dataclasses import dataclass
from typing import Optional
import os

@dataclass
class DeezerConfig:
    cookie_arl: str
    quality: str = 'mp3'
    format: Optional[str] = None
    cookie: Optional[str] = None
    user_id: Optional[str] = None
    user_agent: str = "Mozilla/5.0 (X11; Linux i686; rv:135.0) Gecko/20100101 Firefox/135.0"
    download_folder: str = os.path.join(os.path.expanduser('~'), 'Downloads', 'deezer-downloads')
