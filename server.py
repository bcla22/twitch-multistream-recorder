import logging
from time import sleep
from flask import Flask, redirect, render_template, request, flash
from config import Setting

from twitch import Twitch
from util import get_setting, get_settings, update_settings

# disable server logging
werkzeug_logger = logging.getLogger("werkzeug")
werkzeug_logger.setLevel(logging.ERROR)


class AppServer:
    def __init__(self) -> None:
        self.server = Flask(__name__, static_url_path='', static_folder="out")
        self.server.name = "streamrecorder"
        self.server.secret_key = "secret_sauce"
        self.server.debug = False

        self.server.add_url_rule('/', '/', self.view_status, methods=['GET'])
        self.server.add_url_rule('/recordings', '/recordings', self.view_recordings, methods=['GET'])
        self.server.add_url_rule('/settings', '/settings', self.view_settings, methods=['GET', 'POST'])
        self.server.add_url_rule('/submit', '/submit', self.start_watching_stream, methods=['POST'])
        self.server.add_url_rule('/remove', '/remove', self.stop_watching_stream, methods=['POST'])
        self.server.add_url_rule('/recording_action', '/recording_action', self.handle_recording_action, methods=['POST'])

        self.twitch = Twitch()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, excn_value, exception_traceback):
        pass

    def start(self):
        self.server.run(port=5001)

    def view_status(self):
        """
        Render the status page
        """
        return render_template('status.html',
                               streams=self.twitch.streams,
                               recordings=self.twitch.get_recordings())

    def view_recordings(self):
        """
        Render the recordings page 
        """
        return render_template('recordings.html', recordings=self.twitch.get_recordings())

    def view_settings(self):
        """
        Handle updating settings or rendering the settings page
        """
        if request.method == 'POST':
            if request.form.get('auto_process_recordings') is None:
                update_settings(dict(auto_process_recordings=False))
                self.twitch.processing_loop.join(timeout=1)
                self.twitch.processing_loop = None
            else:
                update_settings(dict(auto_process_recordings=True))
                self.twitch.init_process_loop()
        return render_template('settings.html', settings=get_settings())

    def start_watching_stream(self):
        """
        Start to record one or more Twitch streams
        """
        username = request.form.get('username')
        usernames = request.form.get('usernames')
        if username is None and usernames is None:
            flash('missing username or usernames', 'danger')
            return redirect('/')
        # start watching a single stream
        if isinstance(username, str):
            started, error = self.twitch.start_watching(username)
            if not started and error is not None:
                flash(error, 'danger')
            else:
                flash(
                    f"Started recording {username}'s Twitch stream", 'success')
        # watch multiple streams
        elif isinstance(usernames, str):
            all_errors = []
            for user in usernames.split(','):
                _, error = self.twitch.start_watching(user)
                if error is not None:
                    all_errors.append(error)
                sleep(0.05)
            if len(all_errors) > 0:
                flash(", ".join(all_errors), "danger")
            else:
                flash(f"Started recording {usernames}", 'success')
        return redirect('/')

    def stop_watching_stream(self):
        """
        Stop recording a Twitch stream (and optionally post-process the video)
        """
        username = request.form.get('username')
        if username is None:
            return "missing username", 400
        stopped, error = self.twitch.stop_watching(username)
        if not stopped and error is not None:
            flash(error, 'danger')
        else:
            if get_setting(Setting.AutoProcessRecordings) == True:
                msg = f"Stopped recording {username}'s Twitch stream, processing video in background..."
            else:
                msg = f"Stopped recording {username}'s Twitch stream"
            flash(msg, 'success')
        return redirect('/')

    def handle_recording_action(self):
        """
        Handle actions on recordings, supported: "process", "delete"
        """
        user = request.form.get('user')
        pathname = request.form.get('path')
        action = request.form.get('action')
        # validate
        if not isinstance(action, str) or action not in ["process", "delete"]:
            return "invalid action", 400
        if pathname is None or user is None:
            return "missing path or user", 400
        # perform action
        if action == "process":
            self.twitch.process_recording(f"{user}/{pathname}")
            flash(f"Processed video: {user}/{pathname}", "success")
        elif action == "delete":
            self.twitch.delete_recording(f"{user}/{pathname}")
            flash(f"Deleted video: {user}/{pathname}", "success")
        return redirect('/recordings')
