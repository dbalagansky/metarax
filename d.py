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

class Metarax:
    def __init__(self):
# прикрутить конфигпарсер
        config = ConfigParser.ConfigParser()
        config.read([os.path.expanduser('~/.metarax.cfg'), '/vagrant/.metarax.cfg'])

        self.stdin_path = config.get('daemon', 'stdin_path')
        self.stdout_path = config.get('daemon', 'stdout_path')
        self.stderr_path = config.get('daemon', 'stderr_path')
        self.pidfile_path = config.get('daemon', 'pidfile_path')
        self.pidfile_timeout = config.getint('daemon', 'pidfile_timeout')

        self.host = config.get('socket_server', 'host')
        self.port = config.getint('socket_server', 'port')

        self.logger = logging.getLogger()

        log_level = config.get('logger', 'level')
        numeric_log_level = getattr(logging, config.get('logger', 'level'), None)
        self.logger.setLevel(numeric_log_level)

        self.fh = logging.FileHandler(os.path.expanduser(config.get('logger', 'log_path')))
        self.logger.addHandler(self.fh)

        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((self.host, self.port))
        self.server.listen(config.getint('socket_server', 'max_parallel'))

        self.logger.debug('New socket server spawned on %s:%i' % (self.host, self.port))

    def sampler(self):
        # Sampler function meant to run in separate thread
        # тут вообще нихуя не написано ещё
        pass

    def socket_server(self):
        # Socket server
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
                    self.logger.debug('New client with address: ' + str(addr))
                else:
                    try:
                        data = s.recv(1024)
                        if data:
                            s.send('OK' + data)
                        else:
                            self.logger.debug(inputs)
                            inputs.remove(s)
                            s.close()
                    except socket.error, e:
                        inputs.remove(s)

        self.server.close()
    
    def run(self):
        self.logger.debug('daemon starting')

        # start socket_server
        ss = threading.Thread(name="ss", target=self.socket_server)
        ss.setDaemon = True
        ss.start()

        # start sampler daemon
        sa = threading.Thread(name="sa", target=self.sampler)
        sa.setDaemon = True
        sa.start()

d = Metarax()

# нужно в методе, который вызывается при стопе демона убивать все треды
dr = runner.DaemonRunner(d)
dr.daemon_context.files_preserve = [d.fh.stream, d.server.fileno()]
dr.do_action()
