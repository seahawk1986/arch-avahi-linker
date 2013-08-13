arch-avahi-linker
=================

common media dirs for avahi nfs-shares (using autofs) and local files

Installation:
Install and enable a local NFS server: https://wiki.archlinux.org/index.php/NFS
Install and start avahi-daemon https://wiki.archlinux.org/index.php/Avahi
Enable NFS automounts for autofs: https://wiki.archlinux.org/index.php/Autofs#NFS_Network_mounts
Install Package
Set media directory an vdr recording directory in /etc/avahi-linker/default.cfg
Enable and start avahi-linker.service
```
Usage: avahi-linker.py [options]

Options:
  -h, --help            show this help message and exit
  -c CONFIG_FILE, --config=CONFIG_FILE
```

Note: depending on the network configuration it may take some time until the autofs paths are available.

Writing avahi-service files
Add the directories to your /etc/exports

Example for a vdr recording dir announcement:
/etc/avahi/services/vdr-rec.service

```
<?xml version="1.0" standalone='no'?>
<!DOCTYPE service-group SYSTEM "avahi-service.dtd">
<service-group>
<name replace-wildcards="yes">Recordings on %h</name> ## Name
<service>
       <type>_nfs._tcp</type>
       <port>2049</port>
       <txt-record>path=/srv/vdr/video</txt-record> ## path to shared Folder
       <txt-record>subtype=vdr</txt-record> ## subtype
</service>
</service-group>
```

Example for a movie video dir announcement:
/etc/avahi/services/video-movies.service
```
<?xml version="1.0" standalone='no'?>
<!DOCTYPE service-group SYSTEM "avahi-service.dtd">
<service-group>
<name replace-wildcards="yes">Movies on %h</name> ## Name
<service>
       <type>_nfs._tcp</type>
       <port>2049</port>
       <txt-record>path=/srv/video/Movies</txt-record> ## path to shared Folder
       <txt-record>subtype=video</txt-record> ## subtype
       <txt-record>category=movies</txt-record> ## category
</service>
</service-group>
```

