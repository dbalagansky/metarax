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
        self.clist = []

        # наверное нужно это в init перенести
        self.logger.debug('new socket server spawned')
        self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.s.bind((self.host, self.port))
        self.s.listen(5)

        self.clist.append(self.s)

        while True:
            rs, ws, es = select.select(self.clist, [], [])
# нормально обозвать пермененные
            for s in rs:
                if s == self.s:
                    conn, addr = self.s.accept()
                    self.clist.append(conn)
                else:
                    try:
                        data = s.recv(1024)
                        if data:
                            s.send(data)
                            self.logger.debug('that: %s' % data)
# убрать дублирование кода
                        else:
                            s.close()
                            self.clist.remove(conn)
                            continue
                    except:
                        s.close()
                        #self.clist.remove(conn)
                        continue

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
