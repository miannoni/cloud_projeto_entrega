#!/bin/bash
cd /home/ubuntu/
git clone https://github.com/miannoni/webserver_installer.git
git clone https://github.com/miannoni/scalable_webserver.git
./webserver_installer/instrucoes.sh
python3 ./scalable_webserver/webserver.py
