This README is written to give a brief introduction to the main commands to acquire and/or write data with PICO (custom-made pico-ammeter).
# Usage
The main script to use in order to communicate with PICO is:
```
Pico_reader_converter.py
```
You can can connect to PICO either remotly, paying attention to be on the same network (in case, you could use a VPN service), or through a serial connection. The first one is the default one, but we'll see how to easily switch from one to the other. So, let'start!

## What you would need to change in the code
The main variables you would need to change are:
1. which PICO version you are handling:
    https://github.com/leonardo-favilla/pico-ammeter/blob/6eb37af661189bfb6725cae4b090d31f44daafab/Pico_reader_converter.py#L35
    Up to now, only "pico4" and "pico5" are available.
2. in which folder you want data to be stored:
    https://github.com/leonardo-favilla/pico-ammeter/blob/6eb37af661189bfb6725cae4b090d31f44daafab/Pico_reader_converter.py#L41
    `dataFolder` will be a folder contained at the same level as `Pico_reader_converter.py` script; how the data are actually stored will be explained afterward.

## Main commands
Here we'll try to give a comprehensive and quick overview of the main commands that you can use. The script `Pico_reader_converter.py` comes along with several arguments that we can pass to it, in order to properly use it in several situations. The main flagse are:
1. `-t <acq_time>` sets the acquisition time in seconds.
2. `-s` enables serial connection (default is via ethernet/remote).
3. `-w` enables writing mode, so it produces an output file, in `.txt` format by default, but using also the flag `-r` it will produce a `.root` file as output. Thus:
   * `-w`: writes a file in `.txt` format;
   * `-w -r`: writes a file in `.root` format.
   <br/>The output file will be: `<dataFolder>/<ddmmyy>/<ddmmyy_hhmmss_microseconds.root>`, where `<ddmmyy>` are the day/month/year of the acquisition start and `<ddmmyy_hhmmss_microseconds>` are the exact start time of the acquisition, useful for time-related studies.
4. `-v` enables verbose mode, creating a `.log` file in addition.
5. `-l` enables live monitoring, and must be accompanied by one of the following flags:
    * `--current`: to monitor currents on all 7 channels (so you have to use `-l --current`);
    * `--voltage`: to monitor voltages on all 7 channels (so you have to use `-l --voltage`).
6. `-slow <N>`: reduces writing rate by factor `N` provided by user, i.e. from `400Hz` to `400Hz/<N>`.

    ### Nota Bene 2
    Pay attention that the code in the following line has not been implemented yet in the code, so the flag does not bring you anything else but an error!
    https://github.com/leonardo-favilla/pico-ammeter/blob/6eb37af661189bfb6725cae4b090d31f44daafab/Pico_reader_converter.py#L30

At this point, let's see the actual commands to use and their purpose:
1. To acquire data with PICO for `10` seconds:
    ```
    python3 Pico_reader_converter.py -t 10
    ```
2. To acquire data with PICO for `10` seconds and write to a `.txt` file:
    ```
    python3 Pico_reader_converter.py -t 10 -w
    ```
3. To acquire data with PICO for `10` seconds and write to a `.root` file:
    ```
    python3 Pico_reader_converter.py -t 10 -w -r
    ```
4. To acquire data with PICO for `10` seconds and monitor the currents:
    ```
    python3 Pico_reader_converter.py -t 10 -l --current
    ```
5. To acquire data with PICO for `10` seconds and monitor the voltages:
    ```
    python3 Pico_reader_converter.py -t 10 -l --voltage
    ```
6. To acquire data with PICO for `10` seconds and want to write data to a `.root` file, but with a reduced writing rate, let's say we want to reduce it by a factor `20`:
    ```
    python3 Pico_reader_converter.py -t 10 -w -r -slow 20
    ```

    ### Nota Bene 3
    You can monitor both currents and voltages by running the respective commands in two separate shells. The simultaneous monitoring will be enabled soon!

## Output data format
To be added!!!