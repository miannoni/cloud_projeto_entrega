#!/bin/bash
cd /home/ubuntu/
git clone https://github.com/miannoni/webserver_installer.git
git clone https://github.com/miannoni/database_webserver.git
./webserver_installer/instrucoes.sh
pip3 install pymongo
python3 ./database_webserver/webserver.py
