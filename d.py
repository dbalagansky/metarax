#!/usr/bin/env python
# vim: set fileencoding=utf8 :

import daemon
import lockfile
import time
import sqlite3
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
        #self.pidfile_timeout = config.getint('daemon', 'pidfile_timeout')

        self.sampler_cpu_top_interval = config.getint('sampler', 'cpu_top_interval')
        self.sampler_diskio_util_interval = config.getint('sampler', 'diskio_util_interval')
        self.sampler_vhost_top_interval = config.getint('sampler', 'vhost_top_interval')
        self.sampler_mysql_util_interval = config.getint('sampler', 'mysql_util_interval')
        self.sampler_disk_util_interval = config.getint('sampler', 'disk_util_interval')

        self.host = config.get('socket_server', 'host')
        self.port = config.getint('socket_server', 'port')
        self.max_parallel = config.getint('socket_server', 'max_parallel')

        self.cpu_top_table = config.get('db', 'cpu_top_table')
        self.diskio_util_table = config.get('db', 'diskio_util_table')
        self.vhost_top_table = config.get('db', 'vhost_top_table')
        self.mysql_util_table = config.get('db', 'mysql_util_table')
        self.disk_util_table = config.get('db', 'disk_util_table')

        self.db = config.get('db', 'db_path')

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
        try:
            db_conn = sqlite3.connect(self.db)
            db_cursor = db_conn.cursor()
        except:
            self.logger.exception('fuck')
        while not stop_event.is_set():
            output = subprocess.check_output("iostat -d -xN `df -P /home | tail -1 | cut -f 1 -d ' ' | sed -e 's/^.*\///'` 1 2 | tail -2 | head -1 | awk '{ print $14 }'", shell=True).rstrip()
            try:
                db_cursor.execute('insert into {} values (?, ?)'.format(self.diskio_util_table), (int(time.time()), output))
                db_conn.commit()
            except:
                self.logger.exception('Stop the train!')
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

    def parse_cmd(self, data):
        if str(data.strip()) == 'diskio':
            return 'diskio'

    def get_diskio(self):
        try:
            db_conn = sqlite3.connect(self.db)
            db_cursor = db_conn.cursor()

            db_cursor.execute('select avg(percent) from {} where date between {} and {}'.format(self.diskio_util_table, int(time.time()) - 3600, int(time.time())))
            diskio_avg = db_cursor.fetchone()[0]
            self.logger.debug(diskio_avg)

            db_conn.close()
        except:
            self.logger.exception('stupid database')

        return "%.02f" % diskio_avg

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
                            cmd = self.parse_cmd(data)
                            self.logger.debug('From %s: %s' % (str(addr), cmd))
                            if cmd == 'diskio':
                                s.send('OK %s\n' % self.get_diskio())

                            self.logger.debug(data)
                        else:
                            inputs.remove(s)
                            s.close()
                    except socket.error, e:
                        self.logger.exception('Something wrong in socket_server')
                        inputs.remove(s)

        self.server.close()
    
    def start(self):
        self.logger.info('Metarax is warping out of the Twisting Nether')

        # init database
        try:
            db_conn = sqlite3.connect(self.db)
            db_cursor = db_conn.cursor()
            db_cursor.execute('create table if not exists {} (date integer, top text)'.format(self.cpu_top_table))
            db_cursor.execute('create table if not exists {} (date integer, percent real)'.format(self.diskio_util_table))
            db_cursor.execute('create table if not exists {} (date integer, top text)'.format(self.vhost_top_table))
            db_cursor.execute('create table if not exists {} (date integer, thread integer)'.format(self.mysql_util_table))
            db_cursor.execute('create table if not exists {} (date integer, percent real)'.format(self.disk_util_table))
            db_conn.close()
        except:
            self.logger.exception('DB init failed!')

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

        self.db_conn.close()

def run():
    d = Metarax()

    context = daemon.DaemonContext()
    context.signal_map = {
            signal.SIGTERM: d.stop,
    }
    #context.stdin = d.stdin_path
    #context.stdout = d.stdout_path
    #context.sterr = d.stderr_path
    #context.pidfile = lockfile.FileLock(d.pidfile_path)
    context.files_preserve = [d.fh.stream, d.server.fileno()]

    with context:
        d.start()

if __name__ == "__main__":
    run()
