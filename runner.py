import time
import subprocess

# Configuration
run             = 2                                                             # Run number
minutes         = 10                                                            # Total interval time in minutes
partitions      = 1                                                             # Number of partitions per interval
fileFolder      = "/eos/user/l/lfavilla/GEM/MagnetTest3_Apr2025/picoData"       # Folder to save the data
logFile         = f"log_MagnetTest3_Apr2025_run{str(run)}.log"                  # Log file

seconds         = minutes * 60                                                  # Total interval time in seconds
partition_time  = seconds / partitions                                          # Divide execution time among partitions
counter         = 1                                                             # Initialize partition counter
t0              = time.time()                                                   # Start time
while counter <= partitions:
    t0_         = time.time()
    print(f"Running partition {counter} of {partitions}...")

    command     = [
        "python3", "Pico_reader_converter.py",
        "-t", str(int(partition_time)),
        "-w", "-r",
        "-f", fileFolder
    ]
    
    with open(logFile, "a") as f:
        subprocess.run(command, stdout=f, stderr=f)
    
    tf_         = time.time()
    print(f"Partition {counter} finished in {tf_-t0_} seconds.")
    counter    += 1
tf              = time.time()

files_list      = []
with open(logFile, "r") as f:
    for line in f:
        if "Closing output file" in line:
            files_list.append(line.split()[-1])


print("Data acquisition finished!")
print("Summary:")
print(f"Total time: {tf-t0} seconds")
print(f"Partitions: {partitions}")
print(f"Folder:     {fileFolder}")
print(f"Log file:   {logFile}")
print(f"Files:      {files_list}")