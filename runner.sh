#!/usr/bin/bash
while true; do
    # python3 hello.py >> log.log
    python3 Pico_reader_converter.py -t 300 -w -r -f /eos/user/l/lfavilla/GEM/MagnetTest3_Apr2025/picoData_v2 >> log_pico.log
    sleep 300
done