#!/bin/bash
cd /home/ubuntu/
git clone https://github.com/miannoni/webserver_installer.git
git clone https://github.com/miannoni/Projeto_Cloud.git
./webserver_installer/instrucoes.sh
python3 ./Projeto_Cloud/webserver.py
