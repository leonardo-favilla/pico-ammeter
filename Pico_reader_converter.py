import socket
import sys
import struct
import os
import time
from datetime import datetime, timedelta
from argparse import ArgumentParser
import numpy as np
from statistics import mean
# import serial
import json
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import ROOT
from array import array
from influxdb_client import InfluxDBClient, Point, WriteOptions


plt.ion()

# Arguments #
parser = ArgumentParser(usage="python3 Pico_reader_converter.py -t <time_acq> -w -v") # -s if serial, -r if .root format, -l if live plot
parser.add_argument("-t",       "--time",                 dest="time_acq",            help="Acquisition time in seconds",                                                                   default=10,                               type=int)
parser.add_argument("-s",       "--serial",               dest="serial",              help="Enable serial connection",                                                                                                                          action="store_true")
parser.add_argument("-w",       "--write",                dest="write",               help="Enable writing to file",                                                                                                                            action="store_true")
parser.add_argument("-r",       "--root",                 dest="root",                help="Write in .root format, default in .txt",                                                                                                            action="store_true")
parser.add_argument("-v",       "--verbose",              dest="verbose",             help="Enable verbose mode",                                                                                                                               action="store_true")
parser.add_argument("-l",       "--live_plot",            dest="live_plot",           help="Enable live plot",                                                                                                                                  action="store_true")
parser.add_argument(            "--voltage",              dest="voltage",             help="Enable live voltage plot",                                                                                                                          action="store_true")
parser.add_argument(            "--current",              dest="current",             help="Enable live current plot",                                                                                                                          action="store_true")
parser.add_argument(            "--ch",                   dest="ch",                  help="select channel to plot, default all channel are plotted",                                       default="G3B_G3T_G2B_G2T_G1B_G1T_DRIFT",  type=str)
parser.add_argument("-slow",    "--slow_mode_factor",     dest="slow_mode_factor",    help="Reduce writing rate by factor N provided by user, i.e. from 400Hz to 400Hz/N",                  default=1,                                type=int)
parser.add_argument(            "--grafana",              dest="grafana",             help="Enable writing to InfluxDB",                                                                                                                        action="store_true")
options = parser.parse_args()

# Settings #
pico                = "pico3"
time_acq            = options.time_acq
do_serial           = options.serial
do_write            = options.write
root_format         = options.root
do_verbose          = options.verbose
dataFolder          = "new_folder"
outFolder           = "{}/{}".format(dataFolder, datetime.now().strftime("%d%m%y"))
logFolder           = "{}/{}".format(outFolder, "logs")
if root_format:
    outFilename     = "{}.root".format(datetime.now().strftime("%d%m%y_%H%M%S_%f"))
else:
    outFilename     = "{}.txt".format(datetime.now().strftime("%d%m%y_%H%M%S_%f"))          # f=microsecond
logFilename         = "log_{}.txt".format(datetime.now().strftime("%d%m%y_%H%M%S_%f"))
frameTemplate       = struct.Struct(">5s cI ci ci ci ci ci ci ci 5s")                       # c=char, i=int, s=char[], ">" big endian (most significant byte first)
separator           = ","
convert_volt        = True
convert_curr        = True
convert_temp        = True
live_plot           = options.live_plot
voltage_plot        = options.voltage
current_plot        = options.current
channels_to_plot    = options.ch.split("_")
slow_mode_factor    = options.slow_mode_factor
grafana             = options.grafana
dt                  = 1e-4                                                                  # time interval corresponding to a single timestamp digit; dt is in seconds, example: dt = 0.1 msec = 1e-4 sec

# InfluxDB settings
INFLUXDB_URL    = "http://localhost:8086"
INFLUXDB_TOKEN  = "buP3vnHzoXz-WZMPaGrlgDjXpKlyICtwSUkyDYA4ixqM1gMfXYdsuvMM0n4FWttxTYOMJwWKP7wYfzbaJQsmng=="  # Replace with your actual token
INFLUXDB_ORG    = "organization"
INFLUXDB_BUCKET = "bucket"



# Dictionaries with calibration parameters #
if pico == "pico5":
    with open("./calibrations/pico5/pico5_Calibration_Voltage.json","r") as file:
        CalVoltage = json.load(file)
    with open("./calibrations/pico5/pico5_Calibration_Current.json","r") as file:
        CalCurrent = json.load(file)
elif pico == "pico4":
    with open("./calibrations/pico4/pico4_Calibration_Voltage.json","r") as file:
        CalVoltage = json.load(file)
    with open("./calibrations/pico4/pico4_Calibration_Current.json","r") as file:
        CalCurrent = json.load(file)
elif pico == "pico3":
    with open("./calibrations/pico5/pico5_Calibration_Voltage.json","r") as file:
        CalVoltage = json.load(file)
    with open("./calibrations/pico5/pico5_Calibration_Current.json","r") as file:
        CalCurrent = json.load(file)

# Connection Configuration #
if do_serial:
    hostName        = None
    if pico == "pico4":
        portNumber  = "COM7" # "COM7" per pico4, "COM8" per pico5
    elif pico == "pico5":
        portNumber  = "COM8"
    elif pico == "pico3":
        portNumber  = "COM7"
    baudrate        = 2_000_000
else:
    if pico == "pico4":
        hostName    = "picouart04.na.infn.it" # admin=admin, password=PASSWORD
    elif pico == "pico5":
        hostName    = "picouart05.na.infn.it" # admin=admin, password=PASSWORD
    elif pico == "pico3":
        hostName    = "picouart03.na.infn.it"
    portNumber      = 23
    baudrate        = None

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

        if do_verbose:
            logFile.write("Connection to Pico established\n")
        return s
    
    except Exception as error:
        if do_verbose:
            logFile.write("Something went wrong with the connection to Pico: {}\n".format(error))
            logFile.write("Exiting...\n")
        sys.exit()


channel_map = ["G3B","G3T","G2B","G2T","G1B","G1T","DRIFT"]

def correct_volt(values, CalVoltage):
    # values goes from G3B to DRIFT
    corr_val = []
    for i, ch in enumerate(channel_map):
        corr_val.append(values[i] * CalVoltage[ch]["calFit"]["m"][0] + CalVoltage[ch]["calFit"]["q"][0])
    return corr_val

def correct_curr(values, CalCurrent, labels):
    corr_val = []
    for i, ch in enumerate(channel_map):
        if not ch in CalCurrent:
            corr_val.append(values[i])
        elif labels[i] == b'I' :
            corr_val.append(values[i] * CalCurrent[ch]["calFit_I"]["m"][0] + CalCurrent[ch]["calFit_I"]["q"][0])
        elif labels[i] == b'i' :
            corr_val.append(values[i] * CalCurrent[ch]["calFit_i"]["m"][0] + CalCurrent[ch]["calFit_i"]["q"][0])
        else:
            corr_val.append(values[i])
    return corr_val

def correct_temp(values):
    VRef         = 3.3                              # V
    nbit         = 10                               # number of bits
    corr_val     = []
    for i, ch in enumerate(channel_map):
        value_V = values[i] * VRef/(2**nbit-1)      # convert ADC to Volts
        corr_val.append((value_V - 0.5)/0.01)       # convert Volts to Celsius using the LM50 sensor (ref: https://www.ti.com/lit/ds/symlink/lm50.pdf)
    return corr_val

def write_event_to_file(time_stamp, curr, volt, temp, labels, root_format, outFile, separator=",", tree=None):
    if root_format:
        ts[0]                  = time_stamp

        current_G3B[0]         = curr[0]
        current_G3T[0]         = curr[1]
        current_G2B[0]         = curr[2]
        current_G2T[0]         = curr[3]
        current_G1B[0]         = curr[4]
        current_G1T[0]         = curr[5]
        currrent_DRIFT[0]      = curr[6]

        voltage_G3B[0]         = volt[0]
        voltage_G3T[0]         = volt[1]
        voltage_G2B[0]         = volt[2]
        voltage_G2T[0]         = volt[3]
        voltage_G1B[0]         = volt[4]
        voltage_G1T[0]         = volt[5]
        voltage_DRIFT[0]       = volt[6]

        temperature_G3B[0]     = temp[0]
        temperature_G3T[0]     = temp[1]
        temperature_G2B[0]     = temp[2]
        temperature_G2T[0]     = temp[3]
        temperature_G1B[0]     = temp[4]
        temperature_G1T[0]     = temp[5]
        temperature_DRIFT[0]   = temp[6]

        tree.Fill()
    else:
        line_to_write      = separator.join([str(x) for x in [time_stamp] + curr + volt + temp + labels])
        outFile.write("{}\n".format(line_to_write))


##################
# Initialization #
##################
s = connect_to_pico(do_serial=do_serial, host=hostName, port=portNumber, baud=baudrate)  # connect to the server
if s:
    print("---------------------- Connected to PICO ----------------------")
    if do_verbose:
        logFile.write("Writing data to file {}/{}".format(outFolder, outFilename))
    if do_write:
        print("Writing data to file {}/{}".format(outFolder, outFilename))
        if root_format:
            outFile             = ROOT.TFile("{}/{}".format(outFolder, outFilename), "RECREATE")
            tree                = ROOT.TTree("data_tree", "data_tree")
            # create a branch for each value to be saved
            ts                  = array('d', [0]) # timestamp

            current_G3B         = array('d', [0])
            current_G3T         = array('d', [0])
            current_G2B         = array('d', [0])
            current_G2T         = array('d', [0])
            current_G1B         = array('d', [0])
            current_G1T         = array('d', [0])
            currrent_DRIFT      = array('d', [0])

            voltage_G3B         = array('d', [0])
            voltage_G3T         = array('d', [0])
            voltage_G2B         = array('d', [0])
            voltage_G2T         = array('d', [0])
            voltage_G1B         = array('d', [0])
            voltage_G1T         = array('d', [0])
            voltage_DRIFT       = array('d', [0])

            temperature_G3B     = array('d', [0])
            temperature_G3T     = array('d', [0])
            temperature_G2B     = array('d', [0])
            temperature_G2T     = array('d', [0])
            temperature_G1B     = array('d', [0])
            temperature_G1T     = array('d', [0])
            temperature_DRIFT   = array('d', [0])

            # actually create branches
            tree.Branch("timestamp",        ts,                     "timestamp (1e-4 sec)/D")

            tree.Branch("I_G3B",            current_G3B,            "current_G3B (A)/D")
            tree.Branch("I_G3T",            current_G3T,            "current_G3T (A)/D")
            tree.Branch("I_G2B",            current_G2B,            "current_G2B (A)/D")
            tree.Branch("I_G2T",            current_G2T,            "current_G2T (A)/D")
            tree.Branch("I_G1B",            current_G1B,            "current_G1B (A)/D")
            tree.Branch("I_G1T",            current_G1T,            "current_G1T (A)/D")
            tree.Branch("I_DRIFT",          currrent_DRIFT,         "current_DRIFT (A)/D")

            tree.Branch("V_G3B",            voltage_G3B,            "voltage_G3B (V)/D")
            tree.Branch("V_G3T",            voltage_G3T,            "voltage_G3T (V)/D")
            tree.Branch("V_G2B",            voltage_G2B,            "voltage_G2B (V)/D")
            tree.Branch("V_G2T",            voltage_G2T,            "voltage_G2T (V)/D")
            tree.Branch("V_G1B",            voltage_G1B,            "voltage_G1B (V)/D")
            tree.Branch("V_G1T",            voltage_G1T,            "voltage_G1T (V)/D")
            tree.Branch("V_DRIFT",          voltage_DRIFT,          "voltage_DRIFT (V)/D")

            tree.Branch("T_G3B",            temperature_G3B,        "temperature_G3B (C)/D")
            tree.Branch("T_G3T",            temperature_G3T,        "temperature_G3T (C)/D")
            tree.Branch("T_G2B",            temperature_G2B,        "temperature_G2B (C)/D")
            tree.Branch("T_G2T",            temperature_G2T,        "temperature_G2T (C)/D")
            tree.Branch("T_G1B",            temperature_G1B,        "temperature_G1B (C)/D")
            tree.Branch("T_G1T",            temperature_G1T,        "temperature_G1T (C)/D")
            tree.Branch("T_DRIFT",          temperature_DRIFT,      "temperature_DRIFT (C)/D")

        else:
            tree    = None
            outFile = open("{}/{}".format(outFolder, outFilename), "w")  # output file to save data
            outFile.write("Timestamp,Current_G3B,Current_G3T,Current_G2B,Current_G2T,Current_G1B,Current_G1T,Current_DRIFT,Voltage_G3B,Voltage_G3T,Voltage_G2B,Voltage_G2T,Voltage_G1B,Voltage_G1T,Voltage_DRIFT,Temperature_G3B,Temperature_G3T,Temperature_G2B,Temperature_G2T,Temperature_G1B,Temperature_G1T,Temperature_DRIFT,time_flag,label_G3B,label_G3T,label_G2B,label_G2T,label_G1B,label_G1T,label_DRIFT\n")
else:
    print("Connection to PICO failed")
    sys.exit()

if do_verbose:
    logFile.write("--------------------------------------------------")
t0      = time.time()
curr    = list(np.zeros(7))
volt    = list(np.zeros(7))
temp    = list(np.zeros(7))



# plotting
if live_plot:
    fig,ax = plt.subplots(figsize=(10,6))
    ax.set_xlabel("Time")
    if voltage_plot: 
        ax.set_ylabel("Voltage [V]")
    if current_plot:
        ax.set_ylabel("Current [A]")
    ax.grid(True)
    x_data = []
    y_data = {ch: [] for ch in channels_to_plot}
    box = ax.get_position()
    ax.set_position([box.x0, box.y0, box.width * 0.8, box.height])  # Shrink current axis by 20%    
    

def update_plot(fig, ax, x_data, y_data, unit):
    image = False

    if image:
        img = plt.imread("INFN.jpg") 
        x0, y0 = ax.transData.transform((1.01,0.7))
        ax.figure.figimage(img, x0, y0, alpha=0.5)
    
    plt.title("PICO",size=20)
    if unit=="V":
        label = "V" 
        ax.set_ylabel("Voltage")
    elif unit=="A":
        label = "i" 
        ax.set_ylabel("Current")
    ax.set_xlabel("Timestamp")
    ax.yaxis.set_major_formatter(ticker.EngFormatter(unit=unit))

    style = ticker.EngFormatter(unit=unit, places = 2, sep=" ") # formatter for the measurements in the legend 
    g = lambda x,pos : "{}".format(style(x,pos)) 
    fmt = ticker.FuncFormatter(g)
    
    for ch in channels_to_plot:
        if len(y_data[ch])>=100: 
            y_data[ch]  = y_data[ch][-100:]
            x_data      = x_data[-100:]

        # ax.plot(x_data, y_data[ch], label= ch+"      "+r""+label+" = %.2f $nA$" % (y_data[ch][-1]*10**9)) # for current always in nA
        last_val =  y_data[ch][-1]
        ax.plot(x_data, y_data[ch], label=ch+"    {}".format(fmt(last_val)))
    
    
    plt.legend(loc='center left', bbox_to_anchor=(1.01, 0.5), frameon = True) # Put a legend to the right of the current axis
    # plt.text(0.15,0.91, 'CMS', weight='bold', fontsize=15, transform=plt.gcf().transFigure)
    
    """
    if unit=="A":
        plt.text(0.875, 0.385, r"$I$ = %.2f $nA$" % (y_data["DRIFT"][-1]*10**9), fontsize=8, transform=plt.gcf().transFigure)
        plt.text(0.875, 0.419, r"$I$ = %.2f $nA$" % (y_data["G1T"][-1]*10**9), fontsize=8, transform=plt.gcf().transFigure)
        plt.text(0.875, 0.4525, r"$I$ = %.2f $nA$" % (y_data["G1B"][-1]*10**9), fontsize=8, transform=plt.gcf().transFigure)
        plt.text(0.875, 0.4875, r"$I$ = %.2f $nA$" % (y_data["G2T"][-1]*10**9), fontsize=8, transform=plt.gcf().transFigure)
        plt.text(0.875, 0.525, r"$I$ = %.2f $nA$" % (y_data["G2B"][-1]*10**9), fontsize=8, transform=plt.gcf().transFigure)
        plt.text(0.875, 0.56, r"$I$ = %.2f $nA$" % (y_data["G3T"][-1]*10**9), fontsize=8, transform=plt.gcf().transFigure)
        plt.text(0.875, 0.595, r"$I$ = %.2f $nA$" % (y_data["G3B"][-1]*10**9), fontsize=8, transform=plt.gcf().transFigure)
    elif unit=="V":
        plt.text(0.875, 0.385, r"$V$ = %.2f $V$" % (y_data["DRIFT"][-1]), fontsize=8, transform=plt.gcf().transFigure)
        plt.text(0.875, 0.419, r"$V$ = %.2f $V$" % (y_data["G1T"][-1]), fontsize=8, transform=plt.gcf().transFigure)
        plt.text(0.875, 0.4525, r"$V$ = %.2f $V$" % (y_data["G1B"][-1]), fontsize=8, transform=plt.gcf().transFigure)
        plt.text(0.875, 0.4875, r"$V$ = %.2f $V$" % (y_data["G2T"][-1]), fontsize=8, transform=plt.gcf().transFigure)
        plt.text(0.875, 0.525, r"$V$ = %.2f $V$" % (y_data["G2B"][-1]), fontsize=8, transform=plt.gcf().transFigure)
        plt.text(0.875, 0.56, r"$V$ = %.2f $V$" % (y_data["G3T"][-1]), fontsize=8, transform=plt.gcf().transFigure)
        plt.text(0.875, 0.595, r"$V$ = %.2f $V$" % (y_data["G3B"][-1]), fontsize=8, transform=plt.gcf().transFigure)
    """
    ax.grid(True, alpha=0.35)
    plt.draw()
    plt.pause(0.001)
    ax.cla()



def send_to_influxdb(url, token, org, bucket, time_stamp, measurement_name, fields):
    client      = InfluxDBClient(url=url, token=token, org=org)
    write_api   = client.write_api(write_options=WriteOptions(batch_size=1))

    # Create a single InfluxDB point with multiple fields (one per channel)
    point       = Point(measurement_name).field(fields[0], fields[1]).time(time_stamp, write_precision="s")
    # point.field(fields[0], fields[1])
    # for channel, current in fields.items():
    #     point   = point.field(channel, current)

    # Write to InfluxDB
    write_api.write(bucket=bucket, record=point)
    print(f"Writing to InfluxDB: {point.to_line_protocol()}")
    write_api.close()
    client.close()

if grafana:
    client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
    write_api = client.write_api(write_options=WriteOptions(batch_size=1))

####################
# Data acquisition #
####################
count_time_flip   = 0
count_I           = 0
count_V           = 0
nev_while         = 0
nev               = 0
nev_skip          = 0
nev_notmatching   = 0
nev_error         = 0
nev_written       = 0

bytes             = bytearray()
time_divider      = 1 # 1 if time in seconds, 1000 if time in milliseconds
while (time.time() - t0 <= time_acq/time_divider) or (len(bytes)>0):
    # print("---------------------- Event number: ", nev, " ----------------------")
    # print("Time elapsed:                ", time.time()-t0)
    # if len(bytes):
        # print(f"bytes in memory {len(bytes)}:    {bytes}")
    # print(f"number of bytes in memory:       {len(bytes)}")


    nev_while += 1
    if (time.time() - t0 <= time_acq/time_divider):
        try:
            corrupted_data = False
            if do_serial==False:
                byte = s.recv(50)  # buffersize: pass the number of bytes you want to receive from the socket
            else:
                byte = s.read(50)  # buffersize: pass the number of bytes you want to receive from the serial connection

            # print("byte received:   ", byte)
            bytes.extend(byte)
            # print("total bytes are: ", bytes)
        except Exception as error:
            print("Something went wrong: {}\n".format(error))
            nev_error += 1
            if do_verbose:
                logFile.write("Something went wrong: {}\n".format(error))
                logFile.write("--------------------------------------------------")

    elif (time.time() - t0 > time_acq/time_divider) and s:
        print("Time elapsed: ", time.time()-t0)
        print("Acquisition time reached")
        print("Socket status before shutdown:", s.fileno())
        print("Closing connection to PICO")
        # s.shutdown(socket.SHUT_RDWR)
        s.close()
        s = None

        # Close InfluxDB connection properly
        if grafana:
            write_api.close()
            client.close()
            print("InfluxDB connection closed.")

    else:
        s = None

    ############################
    ### frame reconstruction ###
    ############################
    if ((not s) and (len(bytes) < frameTemplate.size)):
        print("no more bytes to read")
        bytes.clear()
        print("bytes cleared: ", bytes)
        break

    elif (s) and (len(bytes) < frameTemplate.size):
        # print("not enough bytes to unpack")
        continue

    elif (len(bytes) >= frameTemplate.size) and (b"START" in bytes) and (b"/END/" in bytes):
        # remove the bytes until we find the word START

        while bytes[:5] != b"START":
            # print("removing bytes until START")
            # print("removing byte: ", bytes[:1])
            bytes = bytes[1:]
            # print("bytes becomes: ", bytes)

        if len(bytes) < frameTemplate.size:
            # print(f"{len(bytes)} bytes are not enough to unpack")
            continue

    elif (len(bytes) >= frameTemplate.size) and ((b"START" not in bytes) or (b"/END/" not in bytes)):
        continue



    frame = bytes[:frameTemplate.size]
    bytes = bytes[frameTemplate.size:]
    # print("frame: ", frame)
    data  = frameTemplate.unpack(frame)
    # print("data: ", data)


    ###################################
    ### data processing and writing ###
    ###################################
    if (data[0] == b"START") and (data[-1] == b"/END/"):  # check if the frame is complete
        # print("processing data: ", data)
        line = list(data[1:-1])

        if (b"J" in line) or (b"D" in line):  # check if the data must be trashed (if found a "J" or a "D")
            corrupted_data = True

        labels = [x for i, x in enumerate(line) if i % 2 == 0]  # get the labels
        values = [x for i, x in enumerate(line) if i % 2 != 0]  # get the values
        

        if do_verbose:
            logFile.write("Ev. number:                                      {}\n".format(nev))
            logFile.write(str(line) + "\n")
            logFile.write("labels:                                          {}\n".format(labels))
            logFile.write("values:                                          {}\n".format(values))


        #########################################################
        # correct timestamp for label switching (b'W' <-> b'w') #
        #########################################################
        if nev == 0:
            ts0              = values[0]                                        # get the first time stamp
            last_time_flag   = labels[0]                                        # get the first time_flag
        time_flag            = labels[0]                                        # get the time flag
        time_stamp           = -ts0 + values[0] + count_time_flip*(2**32-1)     # 1) normalize to the first timestamp, so ts[0]=0, ts[1]=25, ..., etc, 2) get the time stamp & 3) add the ADC max count to it for each time_flag flip
        if time_flag != last_time_flag:
            count_time_flip += 1
        last_time_flag       = time_flag
        time_s               = timedelta(seconds=time_stamp*dt)
        exact_time_s         = int(t0 + time_s.total_seconds())
        exact_time_ms        = int((t0 + time_s.total_seconds())*1e3)
        exact_time_us        = int((t0 + time_s.total_seconds())*1e6)
        # print(exact_time_s)
        # print(int(time.time()))
        # print(f"timestamp read is:                             {labels[0]}  {values[0]} ---> {time_stamp} ---> {time_s}")
        # print(f"time_flag has changed {count_time_flip} times!\n")
        ###############################
        # Conversion to physical data #
        ###############################


        # other quantities #
        if corrupted_data:
            pass
        elif b'T' in labels:                              # check if the data is a temperature
            if convert_temp:
                temp = correct_temp(values[1:])
            else:
                temp = values[1:]                       # get the temperature values, [1:] is to remove the time stamp

        elif b'V' in labels:                            # check if the data is voltage
            count_V += 1
            if convert_volt:
                volt = correct_volt(values[1:], CalVoltage)
            else:
                volt = values[1:]                       # get the voltage values, [1:] is to remove the time stamp

        elif (b'i' in labels) or (b'I' in labels):      # check if the data is a current
            count_I += 1
            if convert_curr:
                curr = correct_curr(values[1:], CalCurrent, labels[1:])
            else:
                curr = values[1:]                       # get the current values, [1:] is to remove the time stamp
        
        elif (b'p' in labels) or (b'P' in labels) or (b'm' in labels) or (b'M' in labels):
            pass

        
        ########################
        ### SEND TO INFLUXDB ###
        ########################
        if grafana:
            # point = Point("current_measurement").field("current", curr[0]).time(exact_time_us, write_precision="us")
            # point = Point("current_measurement").field("current_G3B", curr[0]).field("current_G3T", curr[1]).field("current_G2B", curr[2]).field("current_G2T", curr[3]).field("current_G1B", curr[4]).field("current_G1T", curr[5]).field("current_DRIFT", curr[6]).time(exact_time_s, write_precision="s")


            # point = Point("current_measurement").tag("channel", "G3B").field("current", curr[0]).time(exact_time_s, write_precision="s")
            if nev%10 == 0:
                # point_I = Point("current_measurement").field("I_G3B", curr[0]).field("I_G3T", curr[1]).field("I_G2B", curr[2]).field("I_G2T", curr[3]).field("I_G1B", curr[4]).field("I_G1T", curr[5]).field("I_DRIFT", curr[6]).time(exact_time_s, write_precision="s")
                point_I = Point("current_measurement").field("I_G3B", curr[0]).field("I_G3T", curr[1]).field("I_G2B", curr[2]).field("I_G2T", curr[3]).field("I_G1B", curr[4]).field("I_G1T", curr[5]).field("I_DRIFT", curr[6]).time(exact_time_ms, write_precision="ms")

                # print(f"Writing to InfluxDB: {point.to_line_protocol()}")
                write_api.write(bucket=INFLUXDB_BUCKET, record=point_I)


                point_V = Point("voltage_measurement").field("V_G3B", volt[0]).field("V_G3T", volt[1]).field("V_G2B", volt[2]).field("V_G2T", volt[3]).field("V_G1B", volt[4]).field("V_G1T", volt[5]).field("V_DRIFT", volt[6]).time(exact_time_s, write_precision="s")

                # print(f"Writing to InfluxDB: {point.to_line_protocol()}")
                write_api.write(bucket=INFLUXDB_BUCKET, record=point_V)


                point_T = Point("temperature_measurement").field("T_G3B", temp[0]).field("T_G3T", temp[1]).field("T_G2B", temp[2]).field("T_G2T", temp[3]).field("T_G1B", temp[4]).field("T_G1T", temp[5]).field("T_DRIFT", temp[6]).time(exact_time_s, write_precision="s")

                # print(f"Writing to InfluxDB: {point.to_line_protocol()}")
                write_api.write(bucket=INFLUXDB_BUCKET, record=point_T)

            # send_to_influxdb(
            #     url=INFLUXDB_URL,
            #     token=INFLUXDB_TOKEN,
            #     org=INFLUXDB_ORG,
            #     bucket=INFLUXDB_BUCKET,
            #     time_stamp=time_stamp,
            #     measurement_name="current_measurement",
            #     # fields={channel: value for channel, value in zip(channel_map, curr)}
            #     fields=["current", curr[6]]
            # )

            # send_to_influxdb(
            #     url=INFLUXDB_URL,
            #     token=INFLUXDB_TOKEN,
            #     org=INFLUXDB_ORG,
            #     bucket=INFLUXDB_BUCKET,
            #     time_stamp=time_stamp,
            #     measurement_name="voltage_measurements",
            #     fields={channel: value for channel, value in zip(channel_map, volt)}
            # )



        if live_plot:
            if nev%65==0 and (not b'm' in labels) and (not b'M' in labels) and (not b'p' in labels) and (not b'P' in labels) and (not corrupted_data):
                if voltage_plot: 
                    unit = "V"
                    x_data.append(time_stamp)
                    for ch in channels_to_plot:
                        y_data[ch].append(volt[channel_map.index(ch)])
                if current_plot:
                    unit = "A"
                    x_data.append(time_stamp)
                    for ch in channels_to_plot:
                        y_data[ch].append(curr[channel_map.index(ch)])
                # print(len(x_data), len(y_data[ch]))
                update_plot(fig, ax, x_data, y_data, unit=unit)
            
        line_to_write = separator.join([str(x) for x in [time_stamp] + [time_s] + curr + volt + temp + labels])
        if do_verbose:
            logFile.write("Timestamp:                                       {}\n".format(time_stamp))
            logFile.write("Time:                                            {}\n".format(time_s))
            logFile.write("Current:                                         {}\n".format(curr))
            logFile.write("Voltage:                                         {}\n".format(volt))
            logFile.write("Temperature:                                     {}\n".format(temp))
            logFile.write("Line to be written to {}:\n\t{}\n".format(outFilename, line_to_write))

        if do_write and not corrupted_data:
            if (nev%slow_mode_factor!=0): # reduce the number of points to be written to file, from 400Hz to 400Hz/N
                pass
            elif (b'p' in labels) or (b'P' in labels) or (b'm' in labels) or (b'M' in labels): # skip the data if it is on 60 measurements
                nev_skip += 1
                pass
            elif (count_I==0) or (count_V==0): # skip the data if it is not complete
                pass
            else:
                nev_written += 1
                if nev_written==1:
                    print("First event written to file occurs at nev = ", nev)
                write_event_to_file(time_stamp=time_stamp,
                                    curr=curr,
                                    volt=volt,
                                    temp=temp,
                                    labels=labels,
                                    root_format=root_format,
                                    outFile=outFile,
                                    separator=separator,
                                    tree=tree)
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
        if nev%10000==0:
            print("Time elapsed:             ", time.time()-t0)
            print("Number of good events:    ", nev)
    else:
        # print("not matching frame: ", data)
        nev_notmatching += 1


if grafana:
    write_api.flush()
    write_api.close()
    client.close()


if live_plot:
    plt.show()


# Close output file
print(f"time_flag has changed:                       {count_time_flip}")
print(f"total number in while loop:                  {nev_while}")
print(f"total number of good events:                 {nev}")
print(f"total number of skipped events:              {nev_skip}")
print(f"total number of written events:              {nev_written}")
print(f"total number of non-matching events:         {nev_notmatching}")
print(f"total number of error events:                {nev_error}")
print(f"total time elapsed:                          {time.time()-t0}")
if do_write:
    print(f"Closing output file:                         {outFolder}/{outFilename}")
    if root_format:
        outFile.Write()
        outFile.Close()
    else:
        outFile.close()

# Close log file
if do_verbose:
    logFile.write("Closing log file\n")
    logFile.close()