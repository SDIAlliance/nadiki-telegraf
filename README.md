# Processor for IPMI Data for Nadiki

Wait until these metrics have been read for a host and timestamp:
- current\_cpu\_power\_consumption\_watts
- current\_dram\_power\_consumption\_watts

Then, add them and store them. If there is already a stored result, calculate the difference
in timestamps and convert the power draw in watts to the consumed joules with this formula:

joules = watt * (fraction of an hour between measurements) * 3600000

The script nadiki-telegraf-processor.py is meant to be run with the execd processor from Telegraf.
