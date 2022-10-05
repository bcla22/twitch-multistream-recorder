import logging
import sys
import webbrowser
from threading import Thread

from server import AppServer

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s')


if __name__ == '__main__':
    # spin up the server
    server = AppServer()
    Thread(target=server.start).start()

    # open up a browser window 
    if '--open' in sys.argv:
        webbrowser.open('http://127.0.0.1:5001')
