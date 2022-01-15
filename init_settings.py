import getopt
import sys

try:
    opts, args = getopt.getopt(sys.argv[1:], "", ["debug", "host=", "port=", "http-host=", "http-path=", "no-popup", "no-crash-log", "no-compression", "no-caching", "no-app_mode"])
except getopt.GetoptError as e:
    print("Error:", e.msg)
    exit(1)

debug = False
host = '127.0.0.1'  # host to listen on 0.0.0.0 for all interfaces, 127.0.0.1 for only localhost
http_host = '127.0.0.1'  # host to open on the webbrowser, can't be 0.0.0.0
http_path = ''  # in order to open a specific page on startup
port = 5005
open_browser = True
crash_log = True
compression = True
caching = True
app_mode = True

for o, a in opts:
    if o == '--host':
        host = a
    elif o == '--port':
        port = int(a)
    elif o == '--http-host':
        http_host = a
    elif o == '--http-path':
        http_path = a
    elif o == '--debug':
        debug = True
    elif o == '--no-popup':
        open_browser = False
    elif o == '--no-crash-log':
        crash_log = False
    elif o == '--no-compression':
        compression = False
    elif o == '--no-caching':
        caching = False
    elif o == '--no-app_mode':
        app_mode = False
