# streamrecorder 

Record multiple Twitch streams at the same time and manage them from a web dashboard.  Inspired by [Junian's script](https://gist.github.com/junian/b41dd8e544bf0e3980c971b0d015f5f6).

## Getting Started 

- Install requirements: `pip3 install -r requirements.txt` 
- Create a `.env` in the project root with `CLIENT_ID` and `CLIENT_SECRET` from the [Twitch Developer Console](https://dev.twitch.tv/console). 
- Run `./bin/start` to connect to Twitch and start up the server
- Open [http://localhost:5001](http://localhost:5001), enter the username you want to record and hit Start.  You should see some console output showing the download progress.  

## How It Works 

[Streamlink](https://streamlink.github.io/) pipes HLS streams from Twitch to a raw recording file in `out/recording/{streamer_name}/{stream_name}.mp4`.  These recordings are passed through [ffmpeg](https://ffmpeg.org/about.html) and stored in `out/processed/{streamer_name}/{stream_name}.mp4`.  This application is a wrapper around those subprocesses. 

The web dashboard keeps track of stream recordings and provides an interface for starting/stopping streams and manually processing recordings mid-stream. 

