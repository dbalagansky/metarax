#!/usr/bin/env python
# vim: set fileencoding=utf8 :
import daemon
from daemon import runner
import time
import logging
import socket
import threading
import select

class Metarax:
    def __init__(self):
# прикрутить конфигпарсер
        self.stdin_path = '/dev/null'
        self.stdout_path = '/dev/tty'
        self.stderr_path = '/dev/tty'
        self.pidfile_path = '/var/tmp/d.pid'
        self.pidfile_timeout = 5

        self.host = ''
        self.port = 50008

        self.logger = logging.getLogger()
        self.logger.setLevel(logging.DEBUG)
        self.fh = logging.FileHandler('/home/vagrant/d.log')
        self.logger.addHandler(self.fh)
        self.logger.debug('New socket server spawned')

        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((self.host, self.port))
        self.server.listen(5)

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
        ss = threading.Thread(name="ss", target=self.socket_server)
        ss.setDaemon = True
        ss.start()

d = Metarax()

# нужно в методе, который вызывается при стопе демона убивать все треды
dr = runner.DaemonRunner(d)
dr.daemon_context.files_preserve = [d.fh.stream, d.server.fileno()]
dr.do_action()
