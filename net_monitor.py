#!/usr/bin/python3
import dbus
import datetime
import socket
from socketserver import UDPServer, BaseRequestHandler

class Handler(BaseRequestHandler):
        def handle(self):
            print("message:", self.request[0])
            print("from:", self.client_address)
            r_hostname, message = self.request[0].decode('utf-8').split(':')
            if message == 'update' and hostname != r_hostname:
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
                print("ignoring message from own hostname {0}".format(r_hostname))

addr = ("", 5555)
hostname = socket.gethostname()
print("listening on %s:%s" % addr)
server = UDPServer(addr, Handler)
server.serve_forever()
