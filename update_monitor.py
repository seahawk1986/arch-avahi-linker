#!/usr/bin/python3
import socket
from gi.repository import GObject
from gi.repository import Gio
import datetime
import argparse

argparser = argparse.ArgumentParser(description='Copy packages in Launchpad.')
argparser.add_argument('-w', '--watch-file', metavar='VIDEODIR/.update',
                       dest='watch_file', default='/srv/vdr/video/.update',
                       help='.update file in vdr video dir (default: /srv/vdr/video/.update)')
argparser.add_argument('-p', '--port',  metavar='PORT', type=int,
                       dest='port', default=5555, help='udp port (default 5555)')
args = vars(argparser.parse_args())

def send_message(message='test'):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, True)
    s.settimeout(5)

    s.sendto(bytes(message, 'UTF-8'), ("<broadcast>", args['port']))
    try:
        print("Response: %s" % s.recv(1024))
    except socket.timeout:
        print("No server found")
    s.close()

def file_changed (monitor, file, unknown, event):
  print("got event:", event)
  if event == Gio.FileMonitorEvent.ATTRIBUTE_CHANGED:
    send_message("{0}:update".format(socket.gethostname()))
    print(".update file changed at {0}".format(datetime.datetime.now()))

file = Gio.file_new_for_path(args["watch_file"])
monitor = file.monitor_file(flags=Gio.FileMonitorFlags(0), cancellable=None)
monitor.connect ("changed", file_changed)
GObject.MainLoop().run()
