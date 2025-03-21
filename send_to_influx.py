import time
import socket
import struct
import numpy as np
from influxdb_client import InfluxDBClient, Point, WriteOptions

# InfluxDB settings
INFLUXDB_URL    = "http://localhost:8086"
INFLUXDB_TOKEN  = "buP3vnHzoXz-WZMPaGrlgDjXpKlyICtwSUkyDYA4ixqM1gMfXYdsuvMM0n4FWttxTYOMJwWKP7wYfzbaJQsmng=="  # Replace with your actual token
INFLUXDB_ORG    = "organization"
INFLUXDB_BUCKET = "new_bucket"

client      = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
write_api   = client.write_api(write_options=WriteOptions(batch_size=1))

# Frame structure
frameTemplate = struct.Struct(">5s cI ci ci ci ci ci ci ci 5s")  

# Connect to electronic tool
hostName = "picouart05.na.infn.it"
portNumber = 23
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((hostName, portNumber))
    t0 = time.time()
except:
    print("Connection failed")
    exit()

bytes = bytearray()
time_divider = 1  # 1 if time in seconds, 1000 if time in milliseconds
time_acq = 1000  # acquisition time in seconds

try:
    while (time.time() - t0 <= time_acq / time_divider) or (len(bytes) > 0):
        if (time.time() - t0 <= time_acq / time_divider):
            try:
                byte = sock.recv(50)  # Receive 50 bytes
                bytes.extend(byte)
            except Exception as error:
                print(f"Something went wrong: {error}")

        elif (time.time() - t0 > time_acq / time_divider) and sock:
            print("Acquisition time reached. Closing connection.")
            sock.close()
            sock = None

        # Frame reconstruction
        if ((not sock) and (len(bytes) < frameTemplate.size)):
            print("No more bytes to read. Clearing buffer.")
            bytes.clear()
            break

        elif (sock) and (len(bytes) < frameTemplate.size):
            continue

        elif (len(bytes) >= frameTemplate.size) and (b"START" in bytes) and (b"/END/" in bytes):
            while bytes[:5] != b"START":
                bytes = bytes[1:]

            if len(bytes) < frameTemplate.size:
                continue

        elif (len(bytes) >= frameTemplate.size) and ((b"START" not in bytes) or (b"/END/" not in bytes)):
            continue

        frame = bytes[:frameTemplate.size]
        bytes = bytes[frameTemplate.size:]
        data = frameTemplate.unpack(frame)

        if (data[0] == b"START") and (data[-1] == b"/END/"):
            line = list(data[1:-1])

            # time_stamp  = int(line[1])*100
            time_stamp  = int(time.time())
            time_stamp_pico = int(line[1] - t0)
            print("time_stamp_pico: ", time_stamp_pico)
            print("time_stamp: ", time_stamp)

            value1      = float(line[3])
            # Write to InfluxDB
            point = Point("current_measurement_1").field("current_1", value1).time(time_stamp, write_precision="s")
            # .field("current_1", value1).time(time_stamp, write_precision="us")
            # print(f"Writing to InfluxDB: {point.to_line_protocol()}")
            write_api.write(bucket=INFLUXDB_BUCKET, record=point)

except KeyboardInterrupt:
    print("Interrupted by user.")

finally:
    # Close InfluxDB connection properly
    write_api.close()
    client.close()
    print("InfluxDB connection closed.")
