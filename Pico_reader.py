import socket
import sys
import struct
import os
import time
from datetime import datetime
from argparse import ArgumentParser
import numpy as np
from statistics import mean
import serial

# Arguments #
parser = ArgumentParser(usage="python3 Pico_reader.py -t <time_acq> -w -v") # -s if serial
parser.add_argument("-t", "--time",    dest="time_acq", help="Acquisition time in seconds", default=10, type=int)
parser.add_argument("-s", "--serial",  dest="serial", help="Enable serial connection", action="store_true")
parser.add_argument("-w", "--write",   dest="write", help="Enable writing to file", action="store_true")
parser.add_argument("-v", "--verbose", dest="verbose", help="Enable verbose mode", action="store_true")
options = parser.parse_args()

# Settings #
time_acq        = options.time_acq
do_serial       = options.serial
do_write        = options.write
do_verbose      = options.verbose
dataFolder      = "/eos/user/l/lfavilla/GEM/MagnetTest3_Apr2025/picoData/"
outFolder       = "{}/{}".format(dataFolder, datetime.now().strftime("%d%m%y"))
logFolder       = "{}/{}".format(outFolder, "logs")
outFilename     = "{}.txt".format(datetime.now().strftime("%d%m%y_%H%M%S_%f"))  # F=Microsecond
frameTemplate   = struct.Struct(">5s cI ci ci ci ci ci ci ci 5s")  # c=char, i=int, s=char[], ">" big endian (most significant byte first)
separator       = ","
logFilename     = "log_{}".format(outFilename)

# Connection Configuration #
if do_serial:
    hostName    = None
    portNumber  = "COM8" # "COM7" per pico4, "COM8" per pico5
    baudrate    = 2_000_000
else:
    hostName    = "GEM-PICO05" # admin=admin, password=PASSWORD
    portNumber  = 23
    baudrate    = None

### Create output folder and file ###
if do_write:
    if os.path.exists(dataFolder):
        if do_verbose:
            if not os.path.exists(logFolder):
                os.makedirs(logFolder)
            # Create log file
            print("Creating log file {}/{}".format(logFolder, logFilename))
            logFile = open(os.path.join(logFolder, logFilename), "w")
            logFile.write("Folder {} already exists\n".format(dataFolder))
        pass
    else:
        if do_verbose:
            if not os.path.exists(logFolder):
                os.makedirs(logFolder)
            # Create log file
            print("Creating log file {}/{}".format(logFolder, logFilename))
            logFile = open(os.path.join(logFolder, logFilename), "w")
            logFile.write("Creating folder {}\n".format(dataFolder))
        os.makedirs(dataFolder)

    if os.path.exists(outFolder):
        if do_verbose:
            logFile.write("Folder {} already exists\n".format(outFolder))
        pass
    else:
        if do_verbose:
            logFile.write("Creating folder {}\n".format(outFolder))
        os.makedirs(outFolder)



# UTILS #
def connect_to_pico(do_serial, host, port, baud):
    try:
        if do_serial==False:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)   # create a TCP/IP socket
            s.connect((host, port))                                 # connect to the server
        else:
            s = serial.Serial(port, baud)                           # connect to the serial port
            print("Connected to serial port {}".format(port))
        if do_verbose:
            logFile.write("Connection to Pico established\n")
        return s
    
    except Exception as error:
        if do_verbose:
            logFile.write("Something went wrong with the connection to Pico: {}\n".format(error))
            logFile.write("Exiting...\n")
        sys.exit()

# Initialization #
s = connect_to_pico(do_serial=do_serial, host=hostName, port=portNumber, baud=baudrate)  # connect to the server
if s:
    print("---------------------- Connected to PICO ----------------------")
    if do_verbose:
        logFile.write("Writing data to file {}\n".format(outFilename))
    if do_write:
        print("Writing data to file {}/{}".format(outFolder, outFilename))
        outFile = open("{}/{}".format(outFolder, outFilename), "w")  # output file to save data
        outFile.write("Timestamp,Current_G3B,Current_G3T,Current_G2B,Current_G2T,Current_G1B,Current_G1T,Current_DRIFT,Voltage_G3B,Voltage_G3T,Voltage_G2B,Voltage_G2T,Voltage_G1B,Voltage_G1T,Voltage_DRIFT,Temperature,time_flag,label_G3B,label_G3T,label_G2B,label_G2T,label_G1B,label_G1T,label_DRIFT\n")
else:
    print("Connection to PICO failed")
    sys.exit()

if do_verbose:
    logFile.write("--------------------------------------------------")
t0      = time.time()
nev     = 0
curr    = list(np.zeros(7))
volt    = list(np.zeros(7))
temp    = list(np.zeros(1))

# Data acquisition #
while time.time() - t0 <= time_acq:
    try:
        corrupted_data = False
        if do_serial==False:
            frame = s.recv(50)  # buffersize: pass the number of bytes you want to receive from the socket
        else:
            frame = s.read(50)  # buffersize: pass the number of bytes you want to receive from the serial connection
        data = frameTemplate.unpack(frame)
        # print(frame)
        if (data[0] == b"START") and (data[-1] == b"/END/"):  # check if the frame is complete
            # print(data)
            line = list(data[1:-1])

            if (b"J" in line) or (b"D" in line):  # check if the data must be trashed (if found a "J" or a "D")
                corrupted_data = True
            print(line)
            labels = [x for i, x in enumerate(line) if i % 2 == 0]  # get the labels
            values = [x for i, x in enumerate(line) if i % 2 != 0]  # get the values
            if nev == 0:
                last_time_flag = labels[0]  # get the first time_flag

            if do_verbose:
                logFile.write("Ev. number:                                      {}\n".format(nev))
                logFile.write(str(line) + "\n")
                logFile.write("labels:                                          {}\n".format(labels))
                logFile.write("values:                                          {}\n".format(values))

            time_flag = labels[0]  # get the time flag
            time_stamp = values[0]  # get the time stamp

            if time_flag != last_time_flag:
                time_stamp += 25 + last_time_stamp

            if b'T' in labels:  # check if the data is a temperature
                temp = [mean([v for (l, v) in zip(labels[1:], values[1:]) if l == b'T'])]  # get the temperature mean value, [1:] is to remove the time stamp

            elif b'V' in labels:  # check if the data is voltage
                volt = values[1:]  # get the voltage values, [1:] is to remove the time stamp

            elif (b'i' in labels) or (b'I' in labels) or (b'p' in labels) or (b'P' in labels) or (
                    b'm' in labels) or (b'M' in labels):  # check if the data is a current
                curr = values[1:]  # get the current values, [1:] is to remove the time stamp

            line_to_write = separator.join([str(x) for x in [time_stamp] + curr + volt + temp + labels])
            last_time_flag, last_time_stamp = time_flag, time_stamp
            #print(line_to_write)
            if do_verbose:
                logFile.write("Timestamp:                                       {}\n".format(time_stamp))
                logFile.write("Current:                                         {}\n".format(curr))
                logFile.write("Voltage:                                         {}\n".format(volt))
                logFile.write("Temperature:                                     {}\n".format(temp))
                logFile.write("Line to be written to {}:\n\t{}\n".format(outFilename, line_to_write))

            if do_write and not corrupted_data:
                outFile.write("{}\n".format(line_to_write))
                if do_verbose:
                    logFile.write("Good data, writing it to file.\n")
            elif do_write and corrupted_data:
                corrupted_data = False
                if do_verbose:
                    logFile.write("DATA CORRUPTED, NOT WRITING IT TO FILE!\n")
            elif not do_write:
                if do_verbose:
                    logFile.write("NOT WRITING IT TO FILE, AS REQUESTED!\n")

            if do_verbose:
                logFile.write("--------------------------------------------------")

            nev += 1
    except Exception as error:
        print("Something went wrong: {}\n".format(error))
        if do_verbose:
            logFile.write("Something went wrong: {}\n".format(error))
            logFile.write("--------------------------------------------------")

# Close output file
if do_write:
    outFile.close()

# Close log file
if do_verbose:
    logFile.write("Closing log file\n")
    logFile.close()