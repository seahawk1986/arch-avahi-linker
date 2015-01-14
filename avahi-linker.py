#!/usr/bin/python2
# -*- coding:utf-8 -*-
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
import argparse
import avahi
import atexit
import codecs
import dbus
import errno
import gettext
import gobject
import ipaddr
import logging
import os
import signal
import socket
import sys
import re
import time
import telnetlib
from dbus import DBusException
from dbus.mainloop.glib import DBusGMainLoop

# Look for nfs shares
TYPE = '_nfs._tcp'

from ConfigParser import SafeConfigParser

##---------------------------------------------------------------------------##
# From https://github.com/senufo/xbmc-vdrclient/blob/master/test_svdrp.py
# Copyright (C) Kenneth Falck 2011.
# edited by Alexander Grothe 2013
# Distribution allowed under the Simplified BSD License.
class SVDRPClient(object):
    def __init__(self, host, port):
        self.telnet = telnetlib.Telnet()
        self.telnet.open(host, port)
        self.read_response()

    def close(self):
        self.telnet.close()

    def send_command(self, line):
        #print '>>>', line
        self.telnet.write(line.encode("UTF-8"))
        self.telnet.write('\n')

    def read_line(self):
        line = self.telnet.read_until('\n', 10).replace('\n', '').replace(
                                                                      '\r', '')
        if len(line) < 4: return None
        return int(line[0:3]), line[3] == '-', line[4:]

    def read_response(self):
        response = []
        line = self.read_line()
        if line: response.append(line)
        while line and line[1]:
            line = self.read_line()
            if line: response.append(line)
        return response
##---------------------------------------------------------------------------##

class SVDRPConnection(object):
    def __init__(self, host, port):
        self.svdrp = SVDRPClient(host, port)

    def sendCommand(self, command=None, expected=250):
        if command:
            try:
                self.svdrp.send_command(command)
                success = False
                answer = []
                for num, flag, message in self.svdrp.read_response():
                    if num == expected: success = True
                    answer.append((num, flag, message))
                self.svdrp.close()
                return success, answer
            except Exception, error:
                logging.exception(Exception, error)
                logging.debug("could not conntect to VDR")
                return False, []

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
                self.config.vdr_running = True
                update_recdir()


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
        self.parser = SafeConfigParser()
        self.parser.optionxform = unicode
        with codecs.open(self.options['config'], 'r', encoding='utf-8') as f:
            self.parser.readfp(f)
        configdir = os.path.dirname(self.options['config'])
        for opt_config in [os.path.join(configdir, u'staticmount.cfg'),
                           os.path.join(configdir, u'localdirs.cfg'),
                           os.path.join(configdir, u'wfe-static.cfg')]:
            try:
                with codecs.open(opt_config, 'r', encoding='utf-8') as f:
                    self.parser.readfp(f)
            except Exception as e:
                print e
        self.mediadir = self.get_setting('targetdirs', 'media', '/tmp')
        self.vdrdir =  self.get_setting('targetdirs', 'vdr', "/tmp")
        self.autofsdir = self.get_setting('options', 'autofsdir', "/net")
        self.use_i18n = self.get_settingb('options', 'use_i18n', False)
        self.nfs_prefix = self.get_setting('options', 'nfs_prefix', "")
        self.nfs_suffix = self.get_setting('options', 'nfs_suffix', "")
        self.use_hostname = self.get_settingb('options', 'use_hostname', False)
        self.static_suffix = self.get_setting('options', 'static_suffix', "")
        self.fat_safe_names = self.get_settingb('options', 'fat_safe_names',
                                                    False)
        self.dbus2vdr = self.get_settingb('options', 'dbus2vdr', False)
        self.svdrp_port = int(self.get_setting('options', 'svdrp_port', 6419))

        if self.parser.has_option('options', 'ip_whitelist'):
            ip_whitelist = self.parser.get('options', 'ip_whitelist').split()
            self.ip_whitelist = []
            for ip in ip_whitelist:
                try:
                    self.ip_whitelist.append(ipaddr.IPNetwork(ip))
                except error as e:
                    logging.error("malformed ip range/address: {0}".format(ip))
                    logging.error(e)
        else:
            self.ip_whitelist = [ipaddr.IPNetwork(u'0.0.0.0/0'),
                                 ipaddr.IPNetwork(u'0::0/0')
                                 ]
        if self.parser.has_option('options', 'ip_blacklist'):
            ip_blacklist = self.parser.get('options', 'ip_blacklist').split()
            self.ip_blacklist = []
            for ip in ip_blacklist:
                try:
                    self.ip_blacklist.append(ipaddr.IPNetwork(ip))
                except error as e:
                    logging.error("malformed ip range/address: {0}".format(ip))
                    logging.error(e)
        else:
            self.ip_blacklist = []


        self.localdirs = {}
        self.mediastaticmounts = {}
        if self.parser.has_section('localdirs'):
            for subtype, directory in self.parser.items('localdirs'):
                self.localdirs[subtype] = directory
        if self.parser.has_section('media_static_mount'):
            for subtype, directory in self.parser.items('media_static_mount'):
                self.mediastaticmounts[subtype] = directory
        self.vdrstaticmounts = {}
        if self.parser.has_section("vdr_static_mount"):
            for subtype, directory in self.parser.items('vdr_static_mount'):
                self.vdrstaticmounts[subtype] = directory

        self.log2file = self.get_settingb('Logging', 'use_file', False)
        self.logfile = self.get_setting('Logging', 'logfile',
                                        '/tmp/avahi-mounter.log')
        self.loglevel = self.get_setting('Logging', 'loglevel', 'DEBUG')
        self.hostname = socket.gethostname()

        if self.log2file:
            logging.basicConfig(
                    filename=self.logfile,
                    level=getattr(logging,self.loglevel),
                    format='%(asctime)-15s %(levelname)-6s %(message)s',
            )
        else:
            logging.basicConfig(
                    level=getattr(logging,self.loglevel),
                    format='%(asctime)-15s %(levelname)-6s %(message)s',
            )
        logging.info(u"Started avahi-linker")
        logging.debug("""
                      Config:
                      media directory: {mediadir}
                      VDR recordings: {vdrdir}
                      autofs directory: {autofsdir}
                      Local directories: {localdirs}
                      VDR Static remote directories: {vdrstaticmounts}
                      Media Static remote directories: {mediastaticmounts}
                      use translations: {use_il8n}
                      use fat_safe_names: {fat_safe_names}
                      Prefix for NFS mounts: {nfs_prefix}
                      Suffix for NFS mounts: {nfs_suffix}
                      use dbus2vdr: {dbus2vdr}
                      SVDRP-Port: {svdrp_port}
                      IP whitelist: {ip_whitelist}
                      IP blacklist: {ip_blacklist}
                      Hostname: {hostname}
                      Log to file: {log2file}
                      Logfile: {logfile}
                      Loglevel: {loglevel}
                      """.format(
                          mediadir=self.mediadir,
                          vdrdir=self.vdrdir,
                          autofsdir=self.autofsdir,
                          use_il8n=self.use_i18n,
                          nfs_prefix=self.nfs_prefix,
                          nfs_suffix=self.nfs_suffix,
                          fat_safe_names=self.fat_safe_names,
                          dbus2vdr=self.dbus2vdr,
                          svdrp_port=self.svdrp_port,
                          ip_whitelist=self.ip_whitelist,
                          ip_blacklist=self.ip_blacklist,
                          hostname=self.hostname,
                          loglevel=self.loglevel,
                          logfile=self.logfile,
                          log2file=self.log2file,
                          vdrstaticmounts=self.vdrstaticmounts,
                          mediastaticmounts=self.mediastaticmounts,
                          localdirs=self.localdirs
                      )
        )

    def get_setting(self, category, setting, default=None):
        if self.parser.has_option(category, setting):
            return self.parser.get(category, setting)
        else:
            return default

    def get_settingb(self, category, setting, default=False):
        if self.parser.has_option(category, setting):
            return self.parser.getboolean(category, setting)
        else:
            return default

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

        for subtype, netdir in config.mediastaticmounts.iteritems():
            subtype, localdir, host = self.prepare(subtype, netdir)
            self.create_link(localdir, os.path.join(self.config.mediadir,
                                                    subtype
                                       )+self.config.static_suffix
            )

        for subtype, netdir in config.vdrstaticmounts.iteritems():
            subtype, localdir, host = self.prepare(subtype, netdir)
            logging.debug('static vdr dir: %s' % netdir)
            logging.debug("path is '%s'" % subtype)
            basedir = os.path.join(self.config.mediadir,subtype)
            target =  self.get_target("vdr", subtype, host)
            vdr_target = self.get_vdr_target(subtype, host)
            self.create_link(localdir, target)
            self.create_link(target, vdr_target)
            self.config.update_recdir()

    def prepare(self, subtype, netdir):
        if self.config.use_i18n is True:
            subtype = get_translation(subtype)[0]
        logging.debug("subtype : %s" % subtype)
        localdir = os.path.join(self.config.autofsdir, netdir)
        host = netdir.split('/')[0]
        logging.debug("Host: {0} type {1}".format(host, type(host)))
        return subtype, localdir, host

    def get_target(self, vdr, subtype, host):
        return os.path.join(
             self.config.mediadir, vdr, subtype, host,
             )+"(for static {0})".format(self.config.hostname)

    def get_vdr_target(self,  subtype, host):
        target = os.path.join(self.config.vdrdir, subtype
                     )+self.config.static_suffix
        logging.debug("vdr target: %s" % target)
        return target

    def unlink_all(self):
        for subtype, localdir in self.config.localdirs.iteritems():
            logging.debug("unlink %s" % os.path.join(self.config.mediadir,
                                                     subtype,
                                                     "local")
            )
            if self.config.use_i18n is True:
                subtype = get_translation(subtype)[0]
            self.unlink(os.path.join(self.config.mediadir, subtype, "local"))

        for subtype, netdir in config.mediastaticmounts.iteritems():
            subtype, localdir , host = self.prepare(subtype, netdir)
            self.unlink(os.path.join(
                self.config.mediadir,
                subtype)+self.config.static_suffix)

        for subtype, netdir in config.vdrstaticmounts.iteritems():
            subtype, localdir , host = self.prepare(subtype, netdir)
            self.unlink(self.get_target("vdr", subtype, host))
            self.unlink(self.get_vdr_target(subtype, host))
            if self.config.job is None:
                self.config.job = gobject.timeout_add(500, update_recdir)

    def create_link(self, origin, target):
        if not os.path.exists(target) and not os.path.islink(target):
            mkdir_p(os.path.dirname(target))
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
        logging.error(u'Avahi error_handler:\n{0}'.format(args[0]))

    def service_added(self, interface, protocol, name, stype, domain, flags):
        logging.debug("Detected service '%s' type '%s' domain '%s' " % (
            name, stype, domain))

        if flags & avahi.LOOKUP_RESULT_LOCAL:
            logging.info(
                "skip local service '%s' type '%s' domain '%s' " % (name,
                                                                    stype,
                                                                    domain)
            )
            pass
        else:
            logging.debug(
                "Checking service '%s' type '%s' domain '%s' " % (name,
                                                                  stype,
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
        attributes = []
        for attribute in txt:
            key, value = u"".join(map(chr, (c for c in attribute))).split("=")
            attributes.append("{key} = {value}".format(key=key, value=value))
        text = unicode(attributes)
        print text
        sharename = u"{share} on {host}".format(share=name, host=host)
        _sharename = u"{share} on {host}: {txt}".format(share=name,
                                                       host=host,
                                                       txt=text)
        logging.debug("avahi-service resolved: %s" % _sharename)
        ip = ipaddr.IPAddress(address)
        if (
            len(
            [ip_range for ip_range in self.config.ip_whitelist if ip in ip_range]
            ) >= 1
        and
            len(
            [ip_range for ip_range in self.config.ip_blacklist if ip in ip_range]
            ) == 0
        ):
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
                    "skipped share {0} on {1}: already used".format(name,
                                                                    host)
                )
        else:
            logging.debug(
                "skipped share {0} on {1}: IP {2} is set to be ignored".format(
                name, host, address)
            )

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
                self.linked.pop(sharename, None)

    def unlink_all(self):
        for share in self.linked:
            self.linked[share].unlink()


class nfsService:
    unsafe_chars = ("<", ">", "?", "&", '"', ":", "|", "\\", "*")

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
        if self.subtype:
            self.basedir = os.path.join(self.config.mediadir,self.subtype)
        else
            self.basedir = self.config.mediadir
        self.origin = self.get_origin()
        self.target = self.get_target()
        if self.subtype == "vdr":
            if not self.wait_for_path(self.origin): return
            else:
                if self.config.use_hostname:
                    self.safe_sharename = (lambda host: host.split('.')[0])(self.host)
                else:
                    self.safe_sharename = self.name
                # sanitize name for windows clients (vdr with
                # --dirnames=,,1
                # or --fat option can display them properly)
                if self.config.fat_safe_names:
                    for char in self.unsafe_chars:
                        self.safe_sharename = self.safe_sharename.replace(char,
                                                    "#{0:x}".format(ord(char)))
                # "/" is not allowed (would create a subdirectory)
                self.safe_sharename = self.safe_sharename.replace(
                                                    "/", "-").replace(" ", "_")
                self.sharename = "".join(
                                         (self.config.nfs_prefix,
                                          self.safe_sharename,
                                          self.config.nfs_suffix)
                                         )


                self.vdr_target = self.get_vdr_target()
                if self.vdr_target:
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
        vdr_target = os.path.join(
            self.config.vdrdir,
            (lambda category: category if category is not None else "")(
                self.category),
             self.sharename
        )
        if os.path.abspath(vdr_target).startswith(self.config.vdrdir):
            return vdr_target
        else:
            logging.error("Path %s is outside of vdrdir - ignoring" % vdr_target)
            return None

    def get_target(self):
        if self.subtype == "vdr":
            target = os.path.join(
                self.basedir,
                (lambda category: category if category is not None else "")(
                    self.category),
                self.sharename
            )
        else:
            return os.path.join(
                self.basedir,
                (lambda category: category if category is not None else "")(
                    self.category),
                self.sharename
            )
        if os.path.abspath(target).startswith(self.basedir):
            return target
        else:
            logging.error("Path %s is outside of basedir - ignoring" % target)
            return None

    def create_link(self):
        if self.target and not os.path.islink(self.target) and not os.path.exists(self.target):
            mkdir_p(os.path.dirname(self.target))
            if self.subtype == "vdr":
                self.target = "%s for %s" % (self.target, self.config.hostname)
            os.symlink(self.origin, self.target)
            logging.debug(
                "created symlink from {origin} to {target} for {share}".format(
                  origin=self.origin, target=self.target, share=self.sharename
                )
            )

    def create_extralink(self, target):
        if target and not os.path.islink(target) and not os.path.exists(target):
            mkdir_p(os.path.dirname(target))
            os.symlink(self.target, target)
            logging.info("created additional symlink for remote VDR dir")

    def wait_for_path(self, path):
        timeout = 0
        while True:
            if os.path.exists(self.origin):
                logging.debug("autofs-path exists: %s" % (self.origin))
                return True
            logging.debug("autofs-path does not exist, try again in 1s")
            time.sleep(1)
            timeout += 1
            if timeout > 120:
                logging.debug(
                    "autofs-path was not available within 120s, giving up")
                return False

    def unlink(self):
        logging.debug("unlinking %s" % self.target)
        if self.target and os.path.islink(self.target):
            os.unlink(self.target)
        if self.vdr_target and self.subtype == "vdr":
            if os.path.islink(self.vdr_target):
                os.unlink(self.vdr_target)
            self.update_recdir()


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
                success, message = SVDRPConnection('127.0.0.1',
                                config.svdrp_port).sendCommand("UPDR")
                logging.info("Update recdir via SVDRP: %s %s", success, message)
    except Exception as error:
        logging.exception(error)
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
    logging.debug('shutting down, vdr is running: %s' % config.vdr_running)
    if config.vdr_running:
        update_recdir()
    gobject.MainLoop().quit()
    sys.exit(0)

class Options():
    def __init__(self):
        """self.parser = OptionParser()
        self.parser.add_option("-c", "--config",
                               dest="config",
                               default='/etc/avahi-linker/default.cfg',
                               metavar="CONFIG_FILE")"""
        self.argparser = argparse.ArgumentParser(
                               description='link avahi announced nfs shares')
        self.argparser.add_argument('-c', '--config', dest="config",
                                    action='append', help='config file(s)',
                                    default='/etc/avahi-linker/default.cfg',
                                    metavar="CONFIG_FILE"
        )

    def get_options(self):
        options = vars(self.argparser.parse_args())
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

