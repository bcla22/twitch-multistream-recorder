import datetime
import enum
import os
import signal
import subprocess
import sys
import time
import typing
from logging import getLogger
from threading import Thread

import requests
from slugify import slugify

from config import Setting, client_id, client_secret
from util import file_size_mb, get_setting

logger = getLogger(__name__)


class TwitchResponseStatus(enum.Enum):
    ONLINE = 0
    OFFLINE = 1
    NOT_FOUND = 2
    UNAUTHORIZED = 3
    ERROR = 4


class RecordingDetail(typing.TypedDict):
    path: str
    processed: bool


class Twitch:
    def __init__(self) -> None:
        # twitch stuff
        self.client_id = client_id
        self.client_secret = client_secret
        self.api_url = "https://api.twitch.tv/helix/streams"
        self.token_url = f"https://id.twitch.tv/oauth2/token?client_id={self.client_id}&client_secret={self.client_secret}&grant_type=client_credentials"
        self.access_token = self.fetch_access_token()

        # streams
        self.root_path = os.getcwd()
        self.streams: dict[str, subprocess.Popen[bytes]] = {}
        self.processing_loop = self.init_process_loop()

        # setup directories
        [os.makedirs(path) for path in [os.path.join(self.root_path, "recorded"), os.path.join(self.root_path, "processed")] if not os.path.isdir(path)]

    def fetch_access_token(self) -> str:
        """
        Fetch a fresh OAuth2 access token from Twitch
        """
        try:
            token_response = requests.post(self.token_url, timeout=15)
            token_response.raise_for_status()
            token = token_response.json()
            logger.info(f'Connected to Twitch with client_id={self.client_id}')
            return token["access_token"]
        except requests.exceptions.RequestException as e:
            logger.error(e)

    def stream_status(self, username: str):
        """
        Determine if a Twitch user is streaming
        """
        info = None
        status = TwitchResponseStatus.ERROR
        try:
            headers = {"Client-ID": self.client_id,
                       "Authorization": f"Bearer {self.access_token}"}
            r = requests.get(
                f"{self.api_url}?user_login={username}", headers=headers, timeout=15)
            r.raise_for_status()
            info = r.json()
            if info is None or not info["data"]:
                status = TwitchResponseStatus.OFFLINE
                logger.info(f"Streamer {username} is offline")
            else:
                status = TwitchResponseStatus.ONLINE
                logger.info(f"Streamer {username} is online and streaming")
        except requests.exceptions.RequestException as e:
            if e.response:
                if e.response.status_code == 401:
                    status = TwitchResponseStatus.UNAUTHORIZED
                if e.response.status_code == 404:
                    status = TwitchResponseStatus.NOT_FOUND
        return status, info

    def start_watching(self, username: str):
        """
        Start watching a Twitch stream 
        Returns:
            bool        indicate if stream started recording or not 
            str | None  any errors if bool was false
        """
        status, info = self.stream_status(username)

        if status is not TwitchResponseStatus.ONLINE:
            logger.error('{} is not online'.format(username))
            return False, f"{username} is not streaming"
        else:
            recorded_path = os.path.join(self.root_path, "recorded", username)
            if not os.path.isdir(recorded_path):
                os.makedirs(recorded_path)
            channels = info["data"]
            channel = next(iter(channels), None)
            filename = '_'.join([datetime.datetime.now().strftime(
                "%Y-%m-%d_%H-%M-%S"), slugify(channel.get("title"))]) + '.mp4'
            recorded_filename = os.path.join(recorded_path, filename)

            self.streams[username] = subprocess.Popen(
                ["streamlink", "--twitch-disable-ads", f"twitch.tv/{username}", "best", "-o", recorded_filename])

            # keep checking until file exists or timer runs out
            start = time.time()
            while True:
                if os.path.isfile(recorded_filename) or time.time() - start > 5:
                    break
                else:
                    time.sleep(0.5)
                    continue

            return True, None

    def stop_watching(self, username):
        """
        Stop watching a Twitch stream
        """
        if username not in self.streams.keys():
            logger.error('could not stop, not watching {}'.format(username))
            return False, f"Not watching {username}"
        else:
            # stop recording process
            proc = self.streams[username]
            proc.send_signal(signal.SIGTERM)
            self.streams.pop(username)
            time.sleep(0.5)

            # process recording
            if get_setting(Setting.AutoProcessRecordings) == True:
                recordings = self.get_recordings()
                if username in recordings.keys():
                    video = recordings[username][len(recordings[username]) - 1]
                    self.process_recording(f"{username}/{video['path']}")

            return True, None

    def get_recordings(self):
        recordings: dict[str, list[RecordingDetail]] = {}
        recordings_dir = os.path.join(self.root_path, "recorded")

        def is_processed(user, video):
            return os.path.isfile(os.path.join(self.root_path, "processed", user, video))

        def size_of(user, video):
            if is_processed(user, video):
                return file_size_mb(os.path.join(self.root_path, "processed", user, video))
            else:
                return file_size_mb(os.path.join(self.root_path, "recorded", user, video))

        for user in os.listdir(recordings_dir):
            # ugh this is annoying! i hate mac sometimes
            if user != '.DS_Store':
                recordings[user] = [dict(path=f, processed=is_processed(user, f), size=size_of(user, f)) for f in os.listdir(
                    os.path.join(recordings_dir, user)) if str(f).endswith('.mp4')]

        return recordings

    def process_recording(self, file_path: str):
        """
        Expect file_path to be like tsm_imperialhal/some_video_name.mp4
        """
        source = os.path.join(self.root_path, "recorded", file_path)
        if not os.path.isfile(source):
            raise FileNotFoundError(
                f"source file {source} does not exist, cannot process")
        if not os.path.isdir(os.path.join(self.root_path, "processed", file_path.split('/')[0])):
            os.makedirs(os.path.join(self.root_path,
                        "processed", file_path.split('/')[0]))
        dest = os.path.join(self.root_path, "processed", file_path)
        try:
            subprocess.run(['ffmpeg', '-err_detect', 'ignore_err',
                           '-i', source, '-c', 'copy', dest, '-y'])
        except Exception as e:
            logger.error(e)

    def delete_recording(self, file_path: str):
        """
        Expect file_path to be like tsm_imperialhal/some_video_name.mp4
        """
        recorded = os.path.join(self.root_path, "recorded", file_path)
        if os.path.isfile(recorded):
            os.remove(recorded)
        processed = os.path.join(self.root_path, "processed", file_path)
        if os.path.isfile(processed):
            os.remove(processed)

    def init_process_loop(self):
        if get_setting(Setting.AutoProcessRecordings) == True:
            def run_loop():
                logger.info('starting background processing loop...')
                while True:
                    for streamer, recordings in self.get_recordings().items():
                        for r in recordings:
                            if streamer not in self.streams.keys() and not r["processed"]:
                                logger.info(
                                    f"processing saved stream: [{streamer}] -> {r['path']}")
                                self.process_recording(
                                    f"{streamer}/{r['path']}")
                    time.sleep(10)

            self.processing_loop = Thread(target=run_loop)
            self.processing_loop.start()
