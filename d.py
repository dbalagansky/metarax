import daemon
from daemon import runner
import time
import logging
import socket

class W:
    def __init__(self):
        self.stdin_path = '/dev/null'
        self.stdout_path = '/dev/tty'
        self.stderr_path = '/dev/tty'
        self.pidfile_path = '/var/tmp/d.pid'
        self.pidfile_timeout = 5

        self.host = ''
        self.port = 50008

    def run(self):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.logger = logging.getLogger()
        self.logger.setLevel(logging.DEBUG)
        self.fh = logging.FileHandler('/home/vagrant/d.log')
        self.logger.addHandler(self.fh)

        self.s.bind((self.host, self.port))
        self.s.listen(5)
        self.conn, self.addr = self.s.accept()
    
        while True:
            data = self.conn.recv(1024)
            if not data:
                break
            self.conn.sendall(data)
            self.logger.debug('that: %s' % data)
        self.conn.close()

w = W()

dr = runner.DaemonRunner(w)
dr.do_action()
