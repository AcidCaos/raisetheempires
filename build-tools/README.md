## Raise The Empires


## Building for Windows
Have both 64-bit as 32-bit python installed.
Copy all code to C:\empires or adapt the build files
See the your save.db is clean without any sessions present, shelf your own save.db if needed.

## 64 bit build:
open cmd
make sure your path includes only 64-bit python, adapt the following line as needed and run:
PATH=C:\Python\Python38\Scripts\;C:\Python\Python38\;C:\Windows\system32;C:\Windows;C:\Windows\System32\Wbem;C:\Windows\System32\WindowsPowerShell\v1.0\;C:\Program Files\Git\cmd
cd c:\empires


PATH=C:\Program Files\Python38\Scripts\;C:\Program Files\Python38\;C:\Windows\system32;C:\Windows;C:\Windows\System32\Wbem;C:\Windows\System32\WindowsPowerShell\v1.0\;C:\Program Files\Git\cmd
cd c:\empires
pip install -r requirements.txt
copy build-tools\empires-server.spec .
pyinstaller empires-server.spec --distpath ..\dist_mini006_x64 --clean

## 32 bit build:
open another cmd
make sure your path includes only 32-bit python, adapt the following line as needed and run:
PATH=C:\Python\Python38-32\Scripts\;C:\Python\Python38-32\;C:\Windows\system32;C:\Windows;C:\Windows\System32\Wbem;C:\Windows\System32\WindowsPowerShell\v1.0\;C:\Program Files\Git\cmd
cd c:\empires
pip install -r requirements.txt
copy build-tools\empires-server.spec .
pyinstaller empires-server.spec --distpath ..\dist_mini006_x86 --clean

## Inno Setup installer
open the build-tools/empires_inno_setup.iss file and play it
test it!




