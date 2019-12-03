
wsjtx-adif.py
---------------

Convert a wsjt-x fox mode .txt log file to ADIF, ignoring logging decisions
made by wsjt-x itself.

Optionally converts timestamps from log's local timezone to UTC for the
ADIF. By default the .txt log is assumed to be in UTC, but if --tz is given,
do the conversion.

As a minimum --mycall should be given. If --power is given, it is logged
as the transmitter power (integer, watts).

Requires python3 and the pytz module for timezone conversions.  On
debian/ubuntu, "apt install python3-pytz" and elsewhere, "pip3 install
pytz".


    usage: wsjtx-adif.py [-h] --mycall N0CALL [--tz Europe/Helsinki] [--in infile]
      [--out outfile] [--power 100]

    optional arguments:
      -h, --help            show this help message and exit
      --mycall N0CALL       My callsign
      --tz Europe/Helsinki  Timezone in log file, defaults to UTC; timestamps will
                            be converted from this timezone to UTC for ADIF
      --in infile           Input file: wsjt-x .txt log file, defaults to STDIN
      --out outfile         Output file: ADIF file, defaults to STDOUT
      --power 100           My transmitter power, in watts, for log rows

