#!/usr/bin/python2
import dbus, gobject, avahi
import atexit
import gettext
import os
import errno
import signal
import sys
from dbus import DBusException
from dbus.mainloop.glib import DBusGMainLoop

# Looks for nfs shares

TYPE = '_nfs._tcp'

from ConfigParser import SafeConfigParser
import codecs

class Config:
    def __init__(self, config='/etc/avahi-linker/default.cfg'):
        parser = SafeConfigParser()
        parser.optionxform = unicode
        with codecs.open(config, 'r', encoding='utf-8') as f:
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
        self.localdirs = {}
        self.staticmounts = {}
        if parser.has_section('localdirs'):
            for subtype, directory in parser.items('localdirs'):
                self.localdirs[subtype] = directory 
        if parser.has_section('staticmount'):
            for subtype, directory in parser.items('staticmount'):
                self.staticmounts[subtype] = directory
        #print self.mediadir
        #print self.vdrdir
        #print self.localdirs

class LocalLinker:
    def __init__(self, config):
        self.config = config
        for subtype, localdir in config.localdirs.iteritems():
            if self.config.use_i18n is True:
                subtype = get_translation(subtype)[0]
            self.create_link(localdir, os.path.join(config.mediadir, subtype, "local"))
        for subtype, netdir in config.staticmounts.iteritems():
            if self.config.use_i18n is True:
                subtype = get_translation(subtype)[0]
            localdir = os.path.join(self.config.autofsdir, netdir)
            host = netdir.split('/')[0]
            print host
            self.create_link(localdir, os.path.join(config.mediadir, subtype, host))

    def unlink_all(self):
        for subtype, localdir in self.config.localdirs.iteritems():
            #print "unlink %s" % os.path.join(self.config.mediadir, subtype, "local")
            if self.config.use_i18n is True:
                subtype = get_translation(subtype)[0]
            self.unlink(os.path.join(self.config.mediadir, subtype, "local"))
        for subtype, netdir in config.staticmounts.iteritems():
            localdir = os.path.join(self.config.autofsdir, netdir)
            if self.config.use_i18n is True:
                subtype = get_translation(subtype)[0]
            host = netdir.split('/')[0]
            self.unlink(os.path.join(self.config.mediadir, subtype, host))

    def create_link(self, origin, target):
        if not os.path.exists(target) and not os.path.islink(target):
            mkdir_p(os.path.dirname(target))
            #print target, "->", origin
            os.symlink(origin, target)

    def unlink(self, target):
        os.unlink(target)
            

class AvahiService:
    def __init__(self, config):
        self.linked = {}
        self.config = config

    def print_error(self, *args):
        print 'error_handler'
        print args[0]
    
    def service_added(self, interface, protocol, name, stype, domain, flags):
        #print "Found service '%s' type '%s' domain '%s' " % (name, stype, domain)

        if flags & avahi.LOOKUP_RESULT_LOCAL:
                # local service, skip
                pass
        server.ResolveService(interface, protocol, name, stype, 
            domain, avahi.PROTO_UNSPEC, dbus.UInt32(0), 
            reply_handler=self.service_resolved, error_handler=self.print_error)

    def service_resolved(self, interface, protocol, name, type,
                 domain, host, aprotocol, address,
                 port, txt, flags):

        share = nfsService(
                       config = config,
                       interface=interface,
                       protocol=protocol, 
                       name=name, 
                       type=type,
                       domain=domain, 
                       host=host, 
                       aprotocol=aprotocol, 
                       address=address,
                       port=port, 
                       txt=txt,
                       flags=flags
                       )
        self.linked[share.name] = share
        #print "active shares:"
        #for share in  self.linked:
        #    print share

    def service_removed(self, interface, protocol, name, type, domain, flags):
        if flags & avahi.LOOKUP_RESULT_LOCAL:
                # local service, skip
                pass
        self.linked[name].unlink()
        del(self.linked[name])

    def unlink_all(self):
        for share in self.linked:
            #print self.linked[share].name
            self.linked[share].unlink()


class nfsService:
    def __init__(self, **attrs):
       self.__dict__.update(**attrs)
       # for each attribute in service description:
       # extract "key=value" pairs after converting dbus.ByteArray to string
       for attribute in self.txt:
            key, value = u"".join(map(chr, (c for c in attribute))).split("=")
            if key == "path":
                self.path = value
            elif key == "subtype":
                self.subtype = value
                print self.subtype
                if self.config.use_i18n is True:
                    self.subtype = get_translation(self.subtype)[0]
                    print "translated: %s" % self.subtype
            elif key == "category":
                self.category = value
                if self.config.use_i18n is True:
                    self.category = get_translation(self.category)[0]
       self.origin = self.get_origin()
       self.target = self.get_target()
       self.create_link()

    def __getattr__(self, attr):
        # return None if attribute is undefined
        return self.__dict__.get(attr, None)

    def get_origin(self):
        return os.path.join(
                     self.config.autofsdir,
                     (lambda host: host.split('.')[0])(self.host),
                     (lambda path: path if not path.startswith(os.path.sep) else path[1:])(self.path)
                     )

    def get_target(self):
        #print "subtype: %s" % self.subtype
        if self.subtype == "vdr":
            basedir = self.config.vdrdir
        else:
            basedir = os.path.join(self.config.mediadir,self.subtype)
        return os.path.join(
                         basedir,
                         (lambda category: category if category is not None else "")(self.category),
                         (lambda host: host.split('.')[0])(self.host),
                         )+self.config.nfs_suffix

    def create_link(self):
        if not os.path.exists(self.target):
            mkdir_p(os.path.dirname(self.target))
            os.symlink(self.origin, self.target)
        if self.subtype == "vdr":
            self.update_recdir()

    def unlink(self):
        #print "unlinking %s" % self.target
        os.unlink(self.target)
        if self.subtype == "vdr":
            self.update_recdir()

    def update_recdir(self):
        try:
            bus = dbus.SystemBus()
            dbus2vdr = bus.get_object('de.tvdr.vdr', '/Recording') 
            dbus2vdr.Update(dbus_interface = 'de.tvdr.vdr.recording')
        except:
            updatepath = os.path.join(vdrdir,".update")
            try:
                syslog("dbus unavailable, fallback to update %s" % updatepath)
                os.utime(updatepath, None)
            except:
                syslog("Create %s"  % updatepath)
                open(updatepath, 'a').close()
                os.chown(updatepath, vdr)

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
            

def sigint(): #signal, frame):
    #print "got %s" % signal
    locallinker.unlink_all()
    avahiservice.unlink_all()
    gobject.MainLoop().quit()
    sys.exit(0)

if __name__ == "__main__":

    loop = DBusGMainLoop()

    bus = dbus.SystemBus(mainloop=loop)
    gettext.install('avahi-linker', '/usr/share/locale', unicode=1)
    config = Config()
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

    atexit.register(sigint)

    gobject.MainLoop().run()

    locallinker.unlink_all()
    avahiservice.unlink_all()
    sys.exit(0)

