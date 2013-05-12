#!/usr/bin/python2
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
import dbus, gobject, avahi
import atexit
import codecs
import gettext
import logging
import os
import errno
import signal
import socket
import sys
import re
import time
import telnetlib
from dbus import DBusException
from dbus.mainloop.glib import DBusGMainLoop

# Looks for nfs shares

TYPE = '_nfs._tcp'

from optparse import OptionParser
from ConfigParser import SafeConfigParser

# Class SVDRPConnection
# http://sourceforge.net/p/svrdpclients/code/HEAD/tree/SVDRPclient/src/libSVDRP/TelnetWrapper.py
# Copyright 2008 Christian Kuehnel
#
# wrapper for the telnet-connection used by the SVDRP
# sends commands to the VDR and converts answer into string array
class SVDRPConnection:

    # store parameters, connect to host
    def __init__(self,host,port):
        self.host = host
        self.port = port
        self.connect()

    # open connection to VDR
    def connect(self):
        self.telnet = telnetlib.Telnet(self.host,self.port)
        self.connectString = self.readAnswer()[0]

    # parse the answer from the VDR and return a string array
    def readAnswer(self):
        done = False
        buffer = ""
        lines = []
        linematcher = re.compile("^\d\d\d-(.*)\n",re.M) #regex for lines
        endmatcher = re.compile("^\d\d\d (.*)\n",re.M) #regex for last line (differs in "-")
        while not done:
            buffer += self.telnet.read_eager()
            #print "Buffer:"+ buffer
            r = linematcher.search(buffer)
            if r:
                #print "match line: "+ r.group(1)
                lines.append(r.group(1))
                l = len(r.group(0))
                buffer = buffer[l:len(buffer)]
            r = endmatcher.search(buffer)
            if r:
                #print "match end: "+ r.group(1)
                lines.append(r.group(1))
                done = True
            time.sleep(0.01)
        return lines

    # send a command string to the VDR, return the answer as string array
    def sendCommand(self,command):
        self.telnet.write(command+"\n");
        return self.readAnswer()

    # close telnet connection VDR
    def close(self):
        self.telnet.close()
        self.connectString = None

class checkDBus4VDR:
    def __init__(self, bus, config, avahi):
        self.config = config
        self.avahi = avahi
        if self.config.dbus2vdr is True:
            self.bus = bus
            self.bus.add_signal_receiver(
                                        self.signal_handler,
                                        interface_keyword='interface',
                                        member_keyword='member'
                                        )
        try:
            self.config.vdr_running = self.check_dbus2vdr()
        except:
            logging.debug("VDR not reachable")
            self.config.vdr_running = False

    def signal_handler(self, *args, **kwargs):
        if kwargs['interface'] == 'de.tvdr.vdr.vdr':
            if kwargs['member'] == "Stop":
		logging.info("VDR stopped")
		self.config.vdr_running = False
            elif kwargs['member'] == "Start":
                logging.info("VDR started")
            elif kwargs['member'] == "Ready":
                logging.info('VDR ready - reenable extradirs')
                self.config.vdr_runnging = True
                [ obj.add_extradir(obj.target) for sharename, obj
                in self.avahi.linked.items() if obj.subtype == "vdr" ]

    def check_dbus2vdr(self):
        self.vdr = self.bus.get_object('de.tvdr.vdr', '/vdr')
        status = self.vdr.Status(dbus_interface='de.tvdr.vdr.vdr')
        if status == "Ready":
            return True


class Config:
    def __init__(self, options):
        self.vdr_running = False
        self.options = options
        self.updateJob = None
        parser = SafeConfigParser()
        parser.optionxform = unicode
        with codecs.open(self.options.config, 'r', encoding='utf-8') as f:
            parser.readfp(f)
        if parser.has_option('targetdirs', 'media'):
            self.mediadir = parser.get('targetdirs','media')
        else:
            self.mediadir = "/tmp"
        if parser.has_option('targetdirs', 'vdr'):
            self.vdrdir =  parser.get('targetdirs','vdr')
        else:
            self.vdrdir = "/tmp"
        if parser.has_option('options', 'autofsdir'):
            self.autofsdir = parser.get('options', 'autofsdir')
        else:
            self.autofsdir = "/net"
        if parser.has_option('options', 'use_i18n'):
            self.use_i18n = parser.getboolean('options', 'use_i18n')
        else:
            self.use_i18n = False
        if parser.has_option('options', 'nfs_suffix'):
            self.nfs_suffix = parser.get('options', 'nfs_suffix')
        else:
            self.nfs_suffix = ""
        if parser.has_option('options', 'static_suffix'):
            self.static_suffix = parser.get('options', 'static_suffix')
        else:
            self.static_suffix = ""
        if parser.has_option('options', 'dbus2vdr'):
            self.dbus2vdr = parser.getboolean('options', 'dbus2vdr')
        else:
             self.dbus2vdr = False
        if parser.has_option('options', 'extradirs'):
            self.extradirs = parser.getboolean('options', 'extradirs')
        else:
            self.extradirs = False
        if parser.has_option('options', 'svdrp_port'):
            self.svdrp_port = parser.getint('options', 'svdrp_port')
        else:
            self.svdrp_port = 6419
        self.localdirs = {}
        self.staticmounts = {}
        if parser.has_section('localdirs'):
            for subtype, directory in parser.items('localdirs'):
                self.localdirs[subtype] = directory
        if parser.has_section('staticmount'):
            for subtype, directory in parser.items('staticmount'):
                self.staticmounts[subtype] = directory
        if parser.has_option('Logging', 'use_file'):
            self.log2file = parser.getboolean('Logging', 'use_file')
        else:
            self.log2file = False
        if parser.has_option('Logging', 'logfile'):
            self.logfile = parser.get('Logging', 'logfile')
        else:
            self.logfile = "/tmp/avahi-mounter.log"
        if parser.has_option('Logging', 'loglevel'):
            self.loglevel = parser.get('Logging', 'loglevel')
        else:
            self.loglevel = "DEBUG"

        self.hostname = socket.gethostname()

        if self.log2file:
            logging.basicConfig(
                    filename=self.logfile,
                    level=getattr(logging,self.loglevel),
                    format='%(asctime)-15s %(levelname)-6s %(message)s',
                    #StreamHandler()
            )
        else:
            logging.basicConfig(
                    level=getattr(logging,self.loglevel),
                    format='%(asctime)-15s %(levelname)-6s %(message)s',
                    #StreamHandler()
            )
        logging.info(u"Started avahi-linker")
        logging.debug("""
                      Config:
                      media directory: {mediadir}
                      VDR recordings: {vdrdir}
                      autofs directory: {autofsdir}
                      Local directories: {localdirs}
                      Static remote directories: {staticmounts}
                      use translations: {use_il8n}
                      Suffix for NFS mounts: {nfs_suffix}
                      use dbus2vdr: {dbus2vdr}
                      use VDR extra dirs: {extradirs}
                      SVDRP-Port: {svdrp_port}
                      Hostname: {hostname}
                      Log to file: {log2file}
                      Logfile: {logfile}
                      Loglevel: {loglevel}
                      """.format(
                          mediadir=self.mediadir,
                          vdrdir=self.vdrdir,
                          autofsdir=self.autofsdir,
                          use_il8n=self.use_i18n,
                          nfs_suffix=self.nfs_suffix,
                          dbus2vdr=self.dbus2vdr,
                          extradirs=self.extradirs,
                          svdrp_port=self.svdrp_port,
                          hostname=self.hostname,
                          loglevel=self.loglevel,
                          logfile=self.logfile,
                          log2file=self.log2file,
                          staticmounts=self.staticmounts,
                          localdirs=self.localdirs
                          )
                      )

    def update_recdir(self):
        if self.updateJob is not None:
            try:
                logging.debug("prevent double update")
                try:
                    gobject.source_remove(self.updateJob)
                except:
                    pass
                self.updateJob = gobject.timeout_add(250, update_recdir)
            except:
                logging.warn("could not inhibit vdr rec updte")
                self.updateJob = gobject.timeout_add(250, update_recdir)
        else:
            self.updateJob = gobject.timeout_add(250, update_recdir)


class LocalLinker:
    def __init__(self, config):
        self.config = config
        for subtype, localdir in config.localdirs.iteritems():
            if self.config.use_i18n is True:
                subtype = get_translation(subtype)[0]
            self.create_link(localdir, os.path.join(config.mediadir, subtype,
                                                    "local"))
        for subtype, netdir in config.staticmounts.iteritems():
            if self.config.use_i18n is True:
                subtype = get_translation(subtype)[0]
            logging.debug("subtype : %s" % subtype)
            localdir = os.path.join(self.config.autofsdir, netdir)
            host = netdir.split('/')[0]
            logging.debug("Host: {0} type {1}".format(host, type(host)))
            if "vdr" == subtype.split(os.sep)[0]:
                logging.debug('static vdr dir: %s' % netdir)
                category = self.get_category(subtype)
                logging.debug("category is '%s'" % category)
                basedir = os.path.join(self.config.mediadir,subtype)
                target =  self.get_target(subtype, host)
                vdr_target = self.get_vdr_target(subtype, host, category)
                self.create_link(localdir, target)
                self.create_link(target, vdr_target)
                self.config.update_recdir()
            else:
                self.create_link(localdir, os.path.join(self.config.mediadir,
                                                        subtype, host)
                                 )

    def get_category(self, subtype):
        elements = subtype.split(os.sep)
        if len(elements) > 0:
            category = os.sep.join(elements[1:])
            if len(category) == 0:
                return ""
            else:
                return category
        else:
            return ""

    def get_target(self, subtype, host):
        return os.path.join(
             self.config.mediadir, subtype,
             host,
             )+"(for static {0})".format(self.config.hostname)

    def get_vdr_target(self,  subtype, host, category):
        target = os.path.join(self.config.vdrdir, category, host
                     )+self.config.static_suffix
        logging.debug("vdr target: %s" % target)
        return target

    def unlink_all(self):
        for subtype, localdir in self.config.localdirs.iteritems():
            logging.debug(
                "unlink %s" % os.path.join(
                                        self.config.mediadir, subtype, "local")
            )
            if self.config.use_i18n is True:
                subtype = get_translation(subtype)[0]
            self.unlink(os.path.join(self.config.mediadir, subtype, "local"))
        for subtype, netdir in config.staticmounts.iteritems():
            localdir = os.path.join(self.config.autofsdir, netdir)
            if self.config.use_i18n is True:
                subtype = get_translation(subtype)[0]
            host = netdir.split('/')[0]
            if "vdr" == subtype.split(os.sep)[0]:
                category = self.get_category(subtype)
                self.unlink(self.get_target(subtype, host))
                self.unlink(self.get_vdr_target(subtype, host, category))
                if self.config.job is None:
                    self.config.job = gobject.timeout_add(
                                                    500, self.update_recdir)
            else:
                self.unlink(os.path.join(self.config.mediadir, subtype, host))

    def create_link(self, origin, target):
        if not os.path.exists(target) and not os.path.islink(target):
            mkdir_p(os.path.dirname(target))
            #print target, "->", origin
            os.symlink(origin, target)

    def unlink(self, target):
        if os.path.islink(target):
            logging.debug("unlink static link %s" % target)
            os.unlink(target)


class AvahiService:
    def __init__(self, config):
        self.linked = {}
        self.config = config
        self.update_recdir = self.config.update_recdir

    def print_error(self, *args):
        logging.error('Avahi error_handler:\n{0}'.format(args[0]))

    def service_added(self, interface, protocol, name, stype, domain, flags):
        logging.debug("Detected service '%s' type '%s' domain '%s' " % (
            name, stype, domain))

        if flags & avahi.LOOKUP_RESULT_LOCAL:
            logging.info(
                "skip local service '%s' type '%s' domain '%s' "
                % (name, stype, domain))
            pass
        else:
            logging.debug(
                "Checking service '%s' type '%s' domain '%s' " % (name, stype,
                                                                 domain)
                         )
            server.ResolveService(
                interface, protocol, name, stype,
                domain, avahi.PROTO_UNSPEC, dbus.UInt32(0),
                reply_handler=self.service_resolved,
                error_handler=self.print_error
            )

    def service_resolved(self, interface, protocol, name, typ,
                 domain, host, aprotocol, address,
                 port, txt, flags):
        sharename = "{share} on {host}".format(share=name,host=host)
        if not sharename in self.linked:
            share = nfsService(
                       config = config,
                       interface=interface,
                       protocol=protocol,
                       name=name,
                       typ=typ,
                       domain=domain,
                       host=host,
                       aprotocol=aprotocol,
                       address=address,
                       port=port,
                       txt=txt,
                       flags=flags,
                       sharename=sharename
                       )
            self.linked[sharename] = share
        else:
            logging.debug(
                "skipped share {0} on {1}: already used".format(name, host))

    def service_removed(self, interface, protocol, name, typ, domain, flags):
        logging.info("service removed: %s %s %s %s %s %s" % (
                                interface, protocol, name, typ, domain, flags))
        if flags & avahi.LOOKUP_RESULT_LOCAL:
                # local service, skip
                pass
        else:
            sharename = next((sharename for sharename, share in
                              self.linked.items() if share.name == name), None)
            logging.debug("removing %s" % sharename)
            if sharename is not None:
                self.linked[sharename].unlink()
                del(self.linked[sharename])

    def unlink_all(self):
        for share in self.linked:
            self.linked[share].unlink()


class nfsService:
    def __init__(self, **attrs):
        self.__dict__.update(**attrs)
        # for each attribute in service description:
        # extract "key=value" pairs after converting dbus.ByteArray to string
        self.update_recdir = self.config.update_recdir
        self.counter = 0
        self.job = None
        for attribute in self.txt:
            key, value = u"".join(map(chr, (c for c in attribute))).split("=")
            if key == "path":
                self.path = value
            elif key == "subtype":
                self.subtype = value
                if self.config.use_i18n is True:
                    original = self.subtype
                    self.subtype = get_translation(self.subtype)[0]
                    logging.debug(
                        "translated {0} to {1}".format(original, self.subtype))
            elif key == "category":
                self.category = value
                if self.config.use_i18n is True:
                    self.category = get_translation(self.category)[0]
        self.basedir = os.path.join(self.config.mediadir,self.subtype)
        self.origin = self.get_origin()
        self.target = self.get_target()
        if self.subtype == "vdr":
            if self.config.extradirs is True:
                if self.category is not None:
                    self.extradir = os.path.join(self.target, self.category)
                    logging.debug("extradir: %s" % self.extradir)
                    self.target = os.path.join(self.target, self.category,
                                               self.category)
                    logging.debug("target: %s" % self.target)
                else:
                    self.extradir = self.target
                self.create_link()
                logging.debug("extradir is %s" % self.extradir)
                if self.add_extradir(self.extradir):
                    self.job = gobject.timeout_add(
                        500, self.add_extradir, self.extradir
                    )
            else:
                self.vdr_target = self.get_vdr_target()
                self.create_link()
                self.create_extralink(self.vdr_target)
                self.update_recdir()
        else:
            self.create_link()


    def __getattr__(self, attr):
        # return None if attribute is undefined
        return self.__dict__.get(attr, None)

    def get_origin(self):
        return os.path.join(
                     self.config.autofsdir,
                     (lambda host: host.split('.')[0])(self.host),
                     (lambda path: path if not path.startswith(
                         os.path.sep) else path[1:])(self.path)
                     )

    def get_vdr_target(self):
        return os.path.join(
            self.config.vdrdir,
            (lambda category: category if category is not None else "")(
                self.category),
            (lambda host: host.split('.')[0])(self.host),
                )+self.config.nfs_suffix

    def get_target(self):
        if self.subtype == "vdr":
            return os.path.join(
                self.basedir,
                (lambda category: category if category is not None else "")(
                    self.category),
                (lambda host: host.split('.')[0])(self.host),
                )+"(for {0})".format(self.config.hostname)
        else:
            return os.path.join(
                self.basedir,
                (lambda category: category if category is not None else "")(
                    self.category),
                (lambda host: host.split('.')[0])(self.host),
                )+self.config.nfs_suffix

    def create_link(self):
        if not os.path.islink(self.target) and not os.path.exists(self.target):
            mkdir_p(os.path.dirname(self.target))
            os.symlink(self.origin, self.target)

    def create_extralink(self, target):
        if not os.path.islink(target) and not os.path.exists(target):
            mkdir_p(os.path.dirname(target))
            os.symlink(self.target, target)
            logging.info("created additional symlink for remote VDR dir")

    def add_extradir(self, target):
        try:
            self.counter  +=1
            if self.config.dbus2vdr is True:
                rec = bus.get_object('de.tvdr.vdr', '/Recordings')
                interface = 'de.tvdr.vdr.recording'
                answer = dbus.Int32(0)
                while int(answer) != 250:
                    answer, message = rec.AddExtraVideoDirectory(
                                dbus.String(target), dbus_interface=interface)
                    logging.debug("trying to add extra dir, got %s %s",
                                  answer, message)
                    time.sleep(0.5)
            else:
                logging.warn("dbus2vdr is required to use extra video dirs")
                self.count = 0
            logging.info("Successfully added extradir %s" % target)
            self.update_recdir()
            return False
        except:
            logging.debug(
                "Could not connect to VDR. Tried %s times to add extradir"
                % self.counter)
            return True

    def rm_extradir(self, target):
        try:
            logging.debug("remove extradir %s" % target)
            if self.config.dbus2vdr is True:
                rec = bus.get_object('de.tvdr.vdr', '/Recordings')
                interface = 'de.tvdr.vdr.recording'
                answer = dbus.Int32(0)
                while int(answer) != 250:
                    answer, message = rec.DeleteExtraVideoDirectory(
                                dbus.String(target), dbus_interface=interface)
                    logging.debug("trying to remove extra dir, got %s %s",
                                                              answer, message)
                    time.sleep(0.5)
        except:
            logging.debug("VDR not reachable, could not remove extradir")

    def unlink(self):
        logging.debug("unlinking %s" % self.target)
        if os.path.islink(self.target):
            os.unlink(self.target)
        if self.subtype == "vdr":
            if self.config.extradirs is True:
                 self.rm_extradir(self.extradir)
            else:
                if os.path.islink(self.vdr_target):
                    os.unlink(self.vdr_target)
            self.update_recdir()

    '''def update_recdir(self):
        try:
            if self.config.dbus2vdr is True:
                bus = dbus.SystemBus()
                dbus2vdr = bus.get_object('de.tvdr.vdr', '/Recording')
                dbus2vdr.Update(dbus_interface = 'de.tvdr.vdr.recording')
                logging.info("Update recdir via dbus")
            else:
                 SVDRPConnection('127.0.0.1',
                                 self.config.svdrp_port).sendCommand("UPDR")
                 logging.info("Update recdir via SVDRP")
        except:
            updatepath = os.path.join(self.config.vdrdir,".update")
            try:
                logging.info(
                    "dbus unavailable, fallback to update %s" % updatepath)
                os.utime(updatepath, None)
                logging.info("set access time for .update")
            except:
                try:
                    logging.info("Create %s"  % updatepath)
                    open(updatepath, 'a').close()
                    os.chown(updatepath, vdr)
                    logging.debug("created .update")
                except: return True
        self.config.job = None
        return False'''

def update_recdir():
    try:
        if config.dbus2vdr is True:
            bus = dbus.SystemBus()
            dbus2vdr = bus.get_object('de.tvdr.vdr', '/Recordings')
            answer = dbus.Int32(0)
            anwer, message = dbus2vdr.Update(
                                    dbus_interface = 'de.tvdr.vdr.recording')
            logging.info("Update recdir via dbus: %s %s", answer, message)
        else:
                SVDRPConnection('127.0.0.1',
                                config.svdrp_port).sendCommand("UPDR")
                logging.info("Update recdir via SVDRP")
    except Exception, error:
        logging.exception(Exception, error)
        updatepath = os.path.join(config.vdrdir,".update")
        try:
            logging.info(
                "dbus unavailable, fallback to update %s" % updatepath)
            os.utime(updatepath, None)
            logging.info("set access time for .update")
        except:
            try:
                logging.info("Create %s"  % updatepath)
                open(updatepath, 'a').close()
                os.chown(updatepath, vdr)
                logging.debug("created .update")
            except: return True
    config.job = None
    config.updateJob = None
    return False

def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc: # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else: raise

def get_translation(*args):
    answer = []
    for arg in args:
        elsub = []
        for element in arg.split('/'):
            elsub.append(_("%s" % element))
        element = "/".join(elsub)
        answer.append(element)
    return answer

def sigint(**args): #signal, frame):
    logging.debug("got %s" % signal)
    locallinker.unlink_all()
    avahiservice.unlink_all()
    update_recdir()
    gobject.MainLoop().quit()
    sys.exit(0)

class Options():
    def __init__(self):
        self.parser = OptionParser()
        self.parser.add_option("-c", "--config",
                               dest="config",
                               default='/etc/avahi-linker/default.cfg',
                               metavar="CONFIG_FILE")

    def get_options(self):
        (options, args) = self.parser.parse_args()
        return options

if __name__ == "__main__":

    loop = DBusGMainLoop()
    options = Options()
    bus = dbus.SystemBus(mainloop=loop)
    gettext.install('avahi-linker', '/usr/share/locale', unicode=1)
    config = Config(options.get_options())
    locallinker = LocalLinker(config)
    server = dbus.Interface( bus.get_object(avahi.DBUS_NAME, '/'),
        'org.freedesktop.Avahi.Server')

    sbrowser = dbus.Interface(bus.get_object(avahi.DBUS_NAME,
        server.ServiceBrowserNew(avahi.IF_UNSPEC,
            avahi.PROTO_UNSPEC, TYPE, 'local', dbus.UInt32(0))),
        avahi.DBUS_INTERFACE_SERVICE_BROWSER)
    avahiservice = AvahiService(config)
    sbrowser.connect_to_signal("ItemNew", avahiservice.service_added)
    sbrowser.connect_to_signal("ItemRemove", avahiservice.service_removed)
    vdr_watchdog = checkDBus4VDR(bus, config, avahiservice)
    atexit.register(sigint)
    signal.signal(signal.SIGTERM, sigint)
    gobject.MainLoop().run()

    locallinker.unlink_all()
    avahiservice.unlink_all()
    sys.exit(0)

