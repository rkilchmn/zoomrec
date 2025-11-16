#!/bin/bash

set -a
source ~/.client.env
set +a

export SERVER_URL="http://localhost:8081"

python test/test_api.py
