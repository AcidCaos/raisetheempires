## Support for servers
### Setting up a server

:file_cabinet:  Download the latest game version [installer](../../releases/latest)

:keyboard: Configure the server by **Command line arguments** when running the executable:

| Synopsis                  | Description                                                    | Notes                                      |
|---------------------------|----------------------------------------------------------------|--------------------------------------------|
|``--port <port_number>``   | Sets the server's running port number                          | Default: `port_number = 5005`<br /> Recommended: `port_number > 1024`           |
|``--host <host_IP>``       | Sets the host to listen on `0.0.0.0` for all <br />interfaces   | Default: `host_IP = 127.0.0.1`<br /> `<host_IP> = 127.0.0.1` for only localhost |
|``--http-host <host_IP>``  | Opened address to the Web Browser on <br />startup              | Default: `host_IP = 127.0.0.1`<br /> `<host_IP>` should not be `0.0.0.0`        |
|``--no-popup``             | The game page is not opened in the Web <br />Browser on startup | Default: the page is opened on startup     |
|``--http-path <page_path>``| Sets a specific page to open on startup                        | Default: `page_path = ''`                  |
|``--debug``                | Sets debugging option to `true`                                | Default: debugging option disabled<br /> Not recommended for servers |
|``--no-crash-log``         | Disables crash log popups                                      | Default: notepads are opened on error<br /> Recommended for servers |
|``--no-compression``       | Disables compression                                           | Default: compression is used<br /> Not recommended for servers |
|``--no-caching``           | Disables caching of modded files                               | Default: caching is used<br /> Not recommended for servers |
|``--no-app_mode``          | Disables app mode in chromium and hides UI elements            | Default: app mode is used<br /> App mode prevents using outdated browsers for other purposes|


:fax: Setup your router and firewall configuration

:speech_balloon: If you are having any issues, contact us on [Discord](https://discord.gg/xrNE6Hg)