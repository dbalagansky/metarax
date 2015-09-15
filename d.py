#!/usr/bin/env python
# vim: set fileencoding=utf8 :

import daemon
from daemon import runner
import time
import logging
import socket
import threading
import select
import ConfigParser
import os
import time
import subprocess

class Metarax:
    def __init__(self):
        config = ConfigParser.ConfigParser()
        config.read([os.path.expanduser('~/.metarax.cfg'), '/vagrant/.metarax.cfg'])

        self.stdin_path = config.get('daemon', 'stdin_path')
        self.stdout_path = config.get('daemon', 'stdout_path')
        self.stderr_path = config.get('daemon', 'stderr_path')
        self.pidfile_path = config.get('daemon', 'pidfile_path')
        self.pidfile_timeout = config.getint('daemon', 'pidfile_timeout')

        self.sampler_cpu_top_interval = config.getint('sampler', 'cpu_top_interval')
        self.sampler_diskio_util_interval = config.getint('sampler', 'diskio_util_interval')
        self.sampler_vhost_top_interval = config.getint('sampler', 'vhost_top_interval')
        self.sampler_mysql_util_interval = config.getint('sampler', 'mysql_util_interval')
        self.sampler_disk_util_interval = config.getint('sampler', 'disk_util_interval')

        self.host = config.get('socket_server', 'host')
        self.port = config.getint('socket_server', 'port')
        self.max_parallel = config.getint('socket_server', 'max_parallel')

        self.logger = logging.getLogger()

        log_level = config.get('logger', 'level')
        numeric_log_level = getattr(logging, config.get('logger', 'level').upper(), None)
        self.logger.setLevel(numeric_log_level)

        self.fh = logging.FileHandler(os.path.expanduser(config.get('logger', 'log_path')))
        self.logger.addHandler(self.fh)

        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def sampler_cpu_top(self):
        self.logger.info('CPU top sampler started!')
        while True:
            time.sleep(self.sampler_cpu_top_interval)

    def sampler_diskio_util(self):
        self.logger.info('Disk I/O utilization sampler started!')
        while True:
            output = subprocess.check_output("iostat -d -xN `df -P /home | tail -1 | cut -f 1 -d ' ' | sed -e 's/^.*\///'` 1 1 | tail -2 | head -1 | awk '{ print $14 }'", shell=True).rstrip()
            self.logger.debug(output)
            time.sleep(self.sampler_diskio_util_interval)

    def sampler_vhost_top(self):
        self.logger.info('Vhost top sampler started!')
        while True:
            time.sleep(self.sampler_vhost_top_interval)

    def sampler_mysql_util(self):
        self.logger.info('MySQL utilization sampler started!')
        while True:
            time.sleep(self.sampler_mysql_util_interval)

    def sampler_disk_util(self):
        self.logger.info('Disk utilization sampler started!')
        while True:
            time.sleep(self.sampler_disk_util_interval)

    def sampler(self):
        # Sampler function meant to run in separate thread
        self.ct = threading.Thread(name="ct", target=self.sampler_cpu_top)
        self.ct.setDaemon = True
        self.ct.start()

        self.diou = threading.Thread(name="diou", target=self.sampler_diskio_util)
        self.diou.setDaemon = True
        self.diou.start()

        self.vt = threading.Thread(name="vt", target=self.sampler_vhost_top)
        self.vt.setDaemon = True
        self.vt.start()

        self.mu = threading.Thread(name="mu", target=self.sampler_mysql_util)
        self.mu.setDaemon = True
        self.mu.start()

        self.du = threading.Thread(name="du", target=self.sampler_disk_util)
        self.du.setDaemon = True
        self.du.start()

    def socket_server(self):
        # Socket server
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((self.host, self.port))
        self.server.listen(self.max_parallel)

        self.logger.info('New socket server spawned on %s:%i' % (self.host, self.port))

        inputs = []

        inputs.append(self.server)

        while inputs:
            rs, ws, es = select.select(inputs, [], [])
# нормально обозвать пермененные
            for s in rs:
                if s is self.server:
                    conn, addr = self.server.accept()
                    conn.setblocking(0)
                    inputs.append(conn)
                    self.logger.info('New client with address: ' + str(addr))
                else:
                    try:
                        data = s.recv(1024)
                        if data:
                            s.send('OK' + data)
                            self.logger.debug(data)
                        else:
                            inputs.remove(s)
                            s.close()
                    except socket.error, e:
                        inputs.remove(s)

        self.server.close()
    
    def run(self):
        self.logger.info('Metarax is warping out of the Twisting Nether')

        # start socket_server thread
        self.ss = threading.Thread(name="ss", target=self.socket_server)
        self.ss.setDaemon = True
        self.ss.start()

        # start sampler thread
        self.sa = threading.Thread(name="sa", target=self.sampler)
        self.sa.setDaemon = True
        self.sa.start()

d = Metarax()

# нужно в методе, который вызывается при стопе демона убивать все треды
dr = runner.DaemonRunner(d)
dr.daemon_context.files_preserve = [d.fh.stream, d.server.fileno()]
dr.do_action()
