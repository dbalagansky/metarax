#!/usr/bin/env python
# vim: set fileencoding=utf8 :
import daemon
from daemon import runner
import time
import logging
import socket
import threading
import select

class W:
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

        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def sampler(self):
        # Sampler function meant to run in separate thread
        # тут вообще нихуя не написано ещё
        pass

    def socket_server(self):
        # Socket server
        clist = []

        # наверное нужно это в init перенести
        self.logger.debug('new socket server spawned')
        self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.s.bind((self.host, self.port))
        self.s.listen(5)

        clist.append(self.s)

        while clist:
            rs, ws, es = select.select(clist, [], [])
# нормально обозвать пермененные
            for s in rs:
                if s is self.s:
                    conn, addr = self.s.accept()
                    conn.setblocking(0)
                    clist.append(conn)
                    self.logger.debug('New client with address: ' + addr)
                else:
                    try:
                        data = s.recv(1024)
                        if data:
                            s.send('OK' + data)
                        else:
                            self.logger.debug(clist)
                            clist.remove(s)
                            s.close()
                    except socket.error, e:
                        clist.remove(s)

        self.s.close()
    
    def run(self):
        self.logger.debug('daemon starting')
        ss = threading.Thread(name="ss", target=self.socket_server)
        ss.setDaemon = True
        ss.start()

w = W()

# нужно в методе, который вызывается при стопе демона убивать все треды
dr = runner.DaemonRunner(w)
dr.daemon_context.files_preserve = [w.fh.stream, w.s.fileno()]
dr.do_action()
