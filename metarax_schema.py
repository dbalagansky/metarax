#!/usr/bin/env python

import sqlite3

conn = sqlite3.connect('metarax.db')

c = conn.cursor()

c.execute('create table if not exists cpu_top (date text, top text)')
c.execute('create table if not exists diskio_util (date text, percent real)')
c.execute('create table if not exists vhost_top (date text, top text)')
c.execute('create table if not exists mysql_util (date text, thread real)')
c.execute('create table if not exists disk_util (date text, percent real)')

conn.close()
