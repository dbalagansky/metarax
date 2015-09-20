#!/usr/bin/env python
# -*- coding: UTF-8 -*-

# enable debugging
import cgi
import cgitb
import socket
import ConfigParser
import sys
import os

cgitb.enable()

def get_metric(metric):
	config = ConfigParser.ConfigParser()
	config.read([os.path.expanduser('~/.metarax.cfg'), '/vagrant/.metarax.cfg', '/etc/metarax.cfg'])

	host = config.get('socket_server', 'host')
	port = config.getint('socket_server', 'port')

	sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	sock.connect((host, port))

	sock.send(metric)
	data = sock.recv(1024)
	sock.close()

	status, value = data.split(' ', 1)

	if status == 'OK':
		return value
	else:
		return 'FAIL'

form = cgi.FieldStorage()
if 'cpu_top' in form:
	action = 'cpu'
	head = ''
	tail = ''
elif 'diskio_util' in form:
	action = 'diskio'
	head = 'Disk I/O: '
	tail = '% for /home, avg for last 10 minutes'
elif 'vhost_top' in form:
	action = 'vhost'
	head = ''
	tail =''
elif 'mysql_util' in form:
	action = 'mysql'
	head = ''
	tail = ''
elif 'disk_util' in form:
	action = 'disk' 
	head = 'Disk Utilization: '
	tail = 'Bytes for /home, changed since last hour'
else:
	action = ''
	head = ''
	tail = ''

if action:
	response = head + get_metric(action) + tail
else:
	response = ''

print "Content-Type: text/html;charset=utf-8"
print
print """
<html>
	<head>
		<title>Metarax Web Interface</title>
	</head>
	<body>
"""
print """
<form method="post" action="metarax.cgi">
<input type="submit" name="cpu_top" value="CPU Top" />
<input type="submit" name="diskio_util" value="Disk I/O Utilization" />
<input type="submit" name="vhost_top" value="Vhost Top" />
<input type="submit" name="mysql_util" value="MySQL Utilization" />
<input type="submit" name="disk_util" value="Disk Utilization" />
<p>%s</p>
</form>
</body>
</html
""" % cgi.escape(response)

