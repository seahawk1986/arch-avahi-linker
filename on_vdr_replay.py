import dbus
import dbus2vdr
import os
from gi.repository import GObject
from dbus.mainloop.glib import DBusGMainLoop

last_file = None


def on_Replay(*args, **kwargs):
    name, path, status, *_ = args
    global last_file
    if status:
        print("Playing %s from %s" % (name, path))
        if not os.lstat(path).st_dev == os.lstat('/srv/vdr/video').st_dev:
            print("let's open a file!")
            last_file = open(os.path.join(path, "index"), 'r')
            
    else:
        print("Stopped Replay")
        try:
            last_file.close()
        except:
            pass
        finally:
            last_file = None

def cleanup(*args, **kwargs):
    global last_file
    print("Cleanup time!")
    try:
        last_file.close()
        print("closed file")
    except:
        pass
    finally:
        last_file = None

if __name__ == '__main__':
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    DBusGMainLoop(set_as_default=True)
    vdr = dbus2vdr.DBus2VDR(dbus.SystemBus(), watchdog=True)
    vdr.onSignal("Replaying", on_Replay)
    vdr.onSignal("Stop", cleanup)
    name, path, status = vdr.Status.IsReplaying()
    on_Replay(name, path, status)
    GObject.MainLoop().run()
