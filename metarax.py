#!/usr/bin/env python
# vim: set fileencoding=utf8 :

import daemon
import daemon.pidfile
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
import smtplib
from email.mime.text import MIMEText

# это будет класс для основных потоков (sampler, socket_server, alerter?)
# хотя, пока можно просто гасить тред sampler'а в треде socket_server. 
#class MetaraxTendril:
    #def ctl_thread(self, thread, target, stop, action):
        #self.logger.debug('Checking if thread %s exists', thread)
        #if not thread:
            #thread = threading.Thread(target=target, args=(stop, ))

        #self.logger.debug('Running acton on %s thread', thread)
        #if action == 'start':
            #self.logger.debug('action start')
            #try:
                #if not thread.is_alive():
                    #self.logger.debug('Thread %s is not alive, starting', thread)
                    #thread.start()
            #except:
                #self.logger.exception('Exception with thread %s', thread)
        #elif action == 'stop':
            #if thread.is_alive():
                #stop.set()
        #else:
            #pass

class Metarax:
    def __init__(self):
        config = ConfigParser.ConfigParser()
        config.read([os.path.expanduser('~/.metarax.cfg'), '/vagrant/.metarax.cfg', '/etc/metarax.cfg'])

        self.ss_stop = threading.Event()
        self.sa_stop = threading.Event()
        self.al_stop = threading.Event()

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

        self.alerter_interval = config.getint('alerter', 'interval')
        self.alerter_from = config.get('alerter', 'email_from')
        self.alerter_to = config.get('alerter', 'email_to')
        self.alerter_email_server = config.get('alerter', 'email_server')

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
        try:
            db_conn = sqlite3.connect(self.db)
            db_cursor = db_conn.cursor()
        except:
            self.logger.exception('where is enterprise manager?')
        while not stop_event.is_set():
            output = subprocess(check_output("df -B 1 --output=avail /home | tail -1", shell=True)).rstrip()
            try:
                db_cursor.execute('insert into {} values (?, ?)'.format(self.disk_util_table), (int(time.time()), output))
                db_conn.commit()
            except:
                self.logger.exception('Something went wrong. If this is a bug, please submit a report to My Oracle Support')
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

    def get_cpu(self):
        pass

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

        return float("%.02f" % diskio_avg)

    def get_vhost(self):
        pass

    def get_mysql(self):
        return 0

    def get_disk(self):
        try:
            db_conn = sqlite3.connect(self.db)
            db_cursor = db_conn.cursor()

            db_cursor.execute('select avg(percent) from {} where date between {} and {}'.format(self.diskio_util_table, int(time.time()) - 3600, int(time.time())))
            diskio_avg = db_cursor.fetchone()[0]
            self.logger.debug(diskio_avg)

            db_conn.close()
        except:
            self.logger.exception('stupid database')

        return int(diskio_avg)

    def usage(self):
        return """Available commands:
cpu
diskio
vhost
mysql
disk
usage
shutdown"""

    def shutdown(self):
        pass
        # self.sa_stop.set()

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

            for s in rs:
                if s is self.server:
                    conn, addr = self.server.accept()
                    conn.setblocking(0)
                    inputs.append(conn)
                    self.logger.info('Client connected: %s' % str(addr))
                else:
                    try:
                        data = s.recv(1024)
                        if data:
                            cmd = str(data.strip())
                            self.logger.debug('From %s: %s' % (str(addr), cmd))
                            if cmd == 'cpu':
                                s.send('OK %d\n' % self.get_cpu())
                            elif cmd == 'diskio':
                                s.send('OK %f\n' % self.get_diskio())
                            elif cmd == 'vhost':
                                s.send('OK %d\n' % self.vhost())
                            elif cmd == 'vhost':
                                s.send('OK %d\n' % self.mysql())
                            elif cmd == 'disk':
                                s.send('OK %d\n' % self.disk())
                            elif cmd == 'shutdown':
                                s.send('OK %s\n' % self.shutdown())
                            elif cmd == 'help':
                                s.send('OK %s\n' % self.usage())
                            else:
                                s.send('FAIL %s\nUse \'help\' for help.\n' % data)
                                self.logger.debug(data)
                        else:
                            self.logger.debug('Client disconncted: %s' % str(addr))
                            inputs.remove(s)
                            s.close()
                    except socket.error, e:
                        self.logger.exception('Something wrong with client: %s' % str(addr))
                        inputs.remove(s)

    def send_email(self, msg):
        try:
            s = smtplib.SMTP(self.alerter_email_server)
            s.sendmail(self.alerter_from, self.alerter_to, msg.as_string())
            s.quit()
        except:
            self.logger.exception('mail is fucked up')

    def alerter(self, stop_event):
        self.logger.info('Alerter started!')

        msg = MIMEText('We have a problem!')
        msg['From'] = self.alerter_from
        msg['To'] = self.alerter_to

        while not stop_event.is_set():
            # Стоит вынести пороги срабатывания в конфигурационный файл
            self.logger.debug(self.get_diskio())
            if self.get_diskio() > 80:
                self.logger.debug('Disk I/O is too high, sending alert')
                del msg['Subject']
                msg['Subject'] = 'Disk I/O is too high'
                self.send_email(msg)
            elif self.get_mysql() > 100:
                self.logger.debug('Number of MySQL threads is too high, sending alert')
                del msg['Subject']
                msg['Subject'] = 'Number of MySQL threads is too high'
                self.send_email(msg)
            elif self.get_disk() > 5000000000:
                self.logger.debug('Disk utilization is too high, sending alert')
                del msg['Subject']
                msg['Subject'] = 'Disk utilization is too high'
                self.send_email(msg)

            stop_event.wait(self.alerter_interval)

    def start(self):
        self.logger.info('Metarax is warping out of the Twisting Nether')

        try:
            db_conn = sqlite3.connect(self.db)
            db_cursor = db_conn.cursor()
            db_cursor.execute('create table if not exists {} (date integer, top text)'.format(self.cpu_top_table))
            db_cursor.execute('create table if not exists {} (date integer, percent real)'.format(self.diskio_util_table))
            db_cursor.execute('create table if not exists {} (date integer, top text)'.format(self.vhost_top_table))
            db_cursor.execute('create table if not exists {} (date integer, thread integer)'.format(self.mysql_util_table))
            db_cursor.execute('create table if not exists {} (date integer, avail integer)'.format(self.disk_util_table))
            db_conn.close()
        except:
            self.logger.exception('DB init failed!')

        # start socket_server thread
        self.ss = threading.Thread(target = self.socket_server, args = (self.ss_stop, ))
        self.ss.start()

        # start sampler thread
        self.sa = threading.Thread(target = self.sampler, args = (self.sa_stop, ))
        self.sa.start()

        # start alerted thread
        self.al = threading.Thread(target = self.alerter, args = (self.al_stop, ))
        self.al.start()

        while True:
            time.sleep(5)

    def stop(self, signum, frame):
        self.logger.info('Sending Metarax back')

        self.ss_stop.set()
        self.sa_stop.set()
        self.al_stop.set()

        self.server.shutdown()
        self.server.close()

def run():
    d = Metarax()

    context = daemon.DaemonContext()
    context.signal_map = {
            signal.SIGTERM: d.stop,
    #        signal.SIGKILL: 'terminate',
    }
    #context.stdin = d.stdin_path
    #context.stdout = d.stdout_path
    #context.sterr = d.stderr_path
    context.pidfile = daemon.pidfile.PIDLockFile(d.pidfile_path)
    context.files_preserve = [d.fh.stream, d.server.fileno()]

    with context:
        d.start()

if __name__ == "__main__":
    run()
