#!/usr/bin/python3

"""
Parse out QSOs from a wsjt-x .txt log file, write to an ADIF log file.
Detect the replies myself, ignoring the logging decision of wsjt-x.

Hessu, OH7LZB/AF5QT 2019-12-03

License: 2-clause BSD

Copyright (c) 2019, Heikki Hannikainen
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

The views and conclusions contained in the software and documentation are those
of the authors and should not be interpreted as representing official policies,
either expressed or implied, of the project.

"""

import datetime
import sys
import re
import pytz
import argparse

# adif band identifiers and rough band edges
BAND_FREQ = {
    '160m': (1800, 2000),
    '80m': (3500, 3800),
    '60m': (5300, 5400),
    '40m': (7000, 7200),
    '30m': (10100, 10150),
    '20m': (14000, 14250),
    '17m': (18068, 18168),
    '15m': (21000, 21450),
    '12m': (24890, 24990),
    '10m': (28000, 29690),
    '6m': (50000, 52000),
    '2m': (140000, 150000),
    '70cm': (430000, 440000),
}

def freq_to_band(freq_khz):
    """
    Convert frequency, in kilohertz, to an adif band identifier
    """
    for band in BAND_FREQ:
        if BAND_FREQ[band][0] <= freq_khz and BAND_FREQ[band][1] >= freq_khz:
            return band
            
    return None

def adif_date(dt):
    "Datetime object to ADIF date, requires an UTC datetime object"
    return dt.strftime("%Y%m%d")

def adif_time(dt):
    "Datetime object to ADIF time, requires an UTC datetime object"
    return dt.strftime("%H%M%S")

def adif_db(d):
    "Signal report in dB, ADIF formatted"
    v = int(d)
    if v >= 0:
        return '+%02d' % v
    else:
        return '-%02d' % (v * -1)

def adif_field(k, v):
    "ADIF field key-length-value encoding"
    if v == None:
        return ''
        
    return '<%s:%d>%s' % (k, len(v), v)
    
def adif_row(h):
    "ADIF row encoding from a dictionary"
    return ' '.join([adif_field(k, h[k]) for k in h]) + ' <eor>\n'


def convert(args):
    "Convert a file"
    
    # Local timezone (or possibly UTC) in wsjtx log file, for converting to UTC in ADIF
    tz_local = pytz.timezone(args.tz)
    
    # parse from either stdin (default), or from a given input file
    if args.infile:
        inf = open(args.infile, 'r')
    else:
        inf = sys.stdin
        
    # write either to stdout (default), or to a given output file
    if args.outfile:
        outf = open(args.outfile, 'w')
    else:
        outf = sys.stdout
    
    outf.write("wsjtx fox ADIF Export<eoh>\n")

    # regular expressions needed to parse entries
    # 2019-11-22 05:25:37  21.091  1  0  0 Sel:  JM1LSQ      -17 QM05
    # 2019-11-22 05:26:00  21.091  0  1  1 Tx1:  JM1LSQ XZ2D -17
    # 2019-11-22 05:26:29  21.091  0  1  1 Rx:   052615  -8 -0.0  300 ~  XZ2D JM1LSQ R+01
    # 2019-11-22 05:26:30  21.091  0  1  1 Log:  JM1LSQ QM05 -17 +01 15m

    re_line = re.compile('^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2})\s+(\d+\.\d+)\s+\d+\s+\d+\s+\d+\s+(\w+:)\s+(.*)')
    re_loc = re.compile('^[A-Z][A-Z][0-9][0-9]$')

    locs = {}  
    ongoing = {}
    logged = {}

    for l in inf:
        g = re_line.match(l)
        if not g:
            #print("no match: %s" % l)
            continue
        
        s_date = g.group(1)
        s_time = g.group(2)
        s_freq_mhz = g.group(3)
        s_linetype = g.group(4)
        s_string = g.group(5)
        
        # Parse timestamp to a datetime object, in log's local time
        d_dt = datetime.datetime.strptime(s_date + ' ' + s_time, '%Y-%m-%d %H:%M:%S')
        #print("date %s freq %s '%s' '%s'" % (d_dt, s_freq_mhz, s_linetype, s_string))
        
        # a station was selected by the operator for working; mark QSO as initiated/replied
        if s_linetype == 'Sel:':
            call, s_db_sent, loc = s_string.split() 
            ongoing[call] = {
                'freq': s_freq_mhz,
                'loc': loc,
                's_db_sent': s_db_sent
            }
        
        elif s_linetype == 'Rx:':
            # We received something
            
            a = s_string.split()
            if len(a) < 8:
                print("rx: Not enough arguments: %s" % l)
                continue
            
            s_tm, db, foo1, foo2, foo3, my, call, report_rx = a
            s_db_rx = report_rx[1:]
            
            # strip <OH0/OH7LZB> to OH0/OH7LZB
            if call.startswith('<') and call.endswith('>'):
                call = call[1:-1]
            
            # If this is an ongoing QSO that we selected, and the report is a R, log it
            if call in ongoing and report_rx.startswith('R'):
                # convert timestamp to UTC
                d_dt_local = tz_local.localize(d_dt)
                d_dt_utc = d_dt_local.astimezone(pytz.utc)
                
                q = ongoing[call]
                o = {
                    'call': call,
                    'mode': 'FT8',
                    'rst_sent': adif_db(q['s_db_sent']),
                    'rst_rcvd': adif_db(s_db_rx),
                    'qso_date': adif_date(d_dt_utc),
                    'time_on': adif_time(d_dt_utc),
                    'qso_date_off': adif_date(d_dt_utc),
                    'time_off': adif_time(d_dt_utc),
                    'band': freq_to_band(float(q['freq'])*1000.0),
                    'freq': '%.3f' % (float(q['freq'])),
                    'station_callsign': args.mycall,
                }
                
                # locator is optional; OH0/OH7LZB calls do not transmit it
                if re_loc.match(q['loc']):
                    o['gridsquare'] = q['loc']
                
                # optionally log our tx power
                if args.power:
                    o['tx_pwr'] = '%d' % args.power
                
                # log it out, forget the ongoing QSO to prevent double logging
                outf.write(adif_row(o))
                del ongoing[call]
            
            
parser = argparse.ArgumentParser(description='Convert wsjt-x fox mode log file to ADIF')
parser.add_argument('--mycall', metavar='N0CALL', type=str, required=True,
                    help='My callsign')
parser.add_argument('--tz', metavar='Europe/Helsinki', type=str, default='UTC',
                    help='Timezone in log file, defaults to UTC; timestamps will be converted from this timezone to UTC for ADIF')
parser.add_argument('--in', metavar='infile', dest='infile', type=str,
                    help='Input file: wsjt-x .txt log file, defaults to STDIN')
parser.add_argument('--out', metavar='outfile', dest='outfile', type=str,
                    help='Output file: ADIF file, defaults to STDOUT')
parser.add_argument('--power', dest='power', metavar='100', type=int,
                    help='My transmitter power, in watts, for log rows')

args = parser.parse_args()
convert(args)
