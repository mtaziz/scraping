#!/bin/sh
/home/innodev/pythoncrawlers/bin/pserve --stop-daemon --pid-file=paster_5000.pid production.ini http_port=5000
/home/innodev/pythoncrawlers/bin/pserve --stop-daemon --pid-file=paster_5001.pid production.ini http_port=5001
