#!/usr/bin/python3
from socketserver import UDPServer, BaseRequestHandler
import argparse
import dbus
import socket
import datetime


class Handler(BaseRequestHandler):
        def handle(self):
            #print("message:", self.request[0])
            #print("from:", self.client_address)
            #print(self.request[0].decode('utf-8'))
            #print(self.client_address[0] in ipList)
            hostname, message = self.request[0].decode('utf-8').split(':')
            if (message == 'update' and not hostname == socket.gethostname()):
                bus = dbus.SystemBus()
                dbus2vdr = bus.get_object('de.tvdr.vdr', '/Recordings')
                answer = dbus.Int32(0)
                anwer, message = dbus2vdr.Update(
                                    dbus_interface = 'de.tvdr.vdr.recording')
                print("update recordings at {0} as requested by {1}".format(datetime.datetime.now(), hostname))
                print("dbus: %s - %s" % (anwer, message))
                socket = self.request[1]
                socket.sendto(bytes("okily dokily",'UTF-8'), self.client_address)
            else:
                print("ignoring local ip address {0}".format(self.client_address[0]))

argparser = argparse.ArgumentParser(description='update vdr recdir on UDP message')
argparser.add_argument('-p', '--port',  metavar='PORT', type=int,
                                              dest='port', default=5555, help='udp port (default 5555)')
args = vars(argparser.parse_args())

addr = ("",  args['port'])
print("listening on %s:%s" % addr)
server = UDPServer(addr, Handler)
server.serve_forever()
