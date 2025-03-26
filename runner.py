import time
import subprocess

# Configuration
minutes         = 5                                                             # Total interval time in minutes
partitions      = 4                                                             # Number of partitions per interval
fileFolder      = "/eos/user/l/lfavilla/GEM/MagnetTest3_Apr2025/picoData"       # Folder to save the data

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
    
    with open("log_pico.log", "a") as log_file:
        subprocess.run(command, stdout=log_file, stderr=log_file)
    
    tf_         = time.time()
    print(f"Partition {counter} finished in {tf_ - t0_} seconds.")
    counter    += 1
tf              = time.time()

print("Data acquisition finished!")
print("Summary:")
print(f"Total time: {tf-t0} seconds")
print(f"Partitions: {partitions}")
print(f"Folder:     {fileFolder}")
print(f"Log file:   log_pico.log")
print(f"Files: ")