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
import subprocess
import signal

class Metarax:
    def __init__(self):
        config = ConfigParser.ConfigParser()
        config.read([os.path.expanduser('~/.metarax.cfg'), '/vagrant/.metarax.cfg'])

        self.ss_stop = threading.Event()
        self.sa_stop = threading.Event()

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

    def sampler_cpu_top(self, stop_event):
        self.logger.info('CPU top sampler started!')
        while not stop_event.is_set():
            stop_event.wait(self.sampler_cpu_top_interval)

    def sampler_diskio_util(self, stop_event):
        self.logger.info('Disk I/O utilization sampler started!')
        while not stop_event.is_set():
            output = subprocess.check_output("iostat -d -xN `df -P /home | tail -1 | cut -f 1 -d ' ' | sed -e 's/^.*\///'` 1 1 | tail -2 | head -1 | awk '{ print $14 }'", shell=True).rstrip()
            self.logger.debug(output)
            stop_event.wait(self.sampler_diskio_util_interval)

    def sampler_vhost_top(self, stop_event):
        self.logger.info('Vhost top sampler started!')
        while not stop_event.is_set():
            stop_event.wait(self.sampler_vhost_top_interval)

    def sampler_mysql_util(self, stop_event):
        self.logger.info('MySQL utilization sampler started!')
        while not stop_event.is_set():
            stop_event.wait(self.sampler_mysql_util_interval)

    def sampler_disk_util(self, stop_event):
        self.logger.info('Disk utilization sampler started!')
        while not stop_event.is_set():
            stop_event.wait(self.sampler_disk_util_interval)

    def sampler(self, stop_event):
        # Sampler function meant to run in separate thread
        self.ct = threading.Thread(target=self.sampler_cpu_top, args = (stop_event, ))
        self.ct.start()

        self.diou = threading.Thread(target=self.sampler_diskio_util, args = (stop_event, ))
        self.diou.start()

        self.vt = threading.Thread(target=self.sampler_vhost_top, args = (stop_event, ))
        self.vt.start()

        self.mu = threading.Thread(target=self.sampler_mysql_util, args = (stop_event, ))
        self.mu.start()

        self.du = threading.Thread(target=self.sampler_disk_util, args = (stop_event, ))
        self.du.start()

    def socket_server(self, stop_event):
        # Socket server
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((self.host, self.port))
        self.server.listen(self.max_parallel)

        self.logger.info('New socket server spawned on %s:%i' % (self.host, self.port))

        inputs = [self.server]
        outputs = []

        while inputs and not stop_event.is_set():
            try:
                rs, ws, es = select.select(inputs, outputs, [], 1)
            except select.error:
                break
            except socket.error:
                break

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
    
    def start(self):
        self.logger.info('Metarax is warping out of the Twisting Nether')

        # start socket_server thread
        self.ss = threading.Thread(target=self.socket_server, args=(self.ss_stop, ))
        self.ss.start()

        # start sampler thread
        self.sa = threading.Thread(target=self.sampler, args=(self.sa_stop, ))
        self.sa.start()
        while True:
            time.sleep(5)

    def stop(self, signum, frame):
        self.logger.info('Sending Metarax back')

        self.ss_stop.set()
        self.sa_stop.set()

        self.server.shutdown()

def run():
    d = Metarax()

    context = daemon.DaemonContext()
    context.signal_map = {
            signal.SIGTERM: d.stop,
    }
    context.files_preserve = [d.fh.stream, d.server.fileno()]

    with context:
        d.start()

if __name__ == "__main__":
    run()
