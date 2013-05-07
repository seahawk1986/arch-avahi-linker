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
<name replace-wildcards="yes">Videos on %h</name> ## Name
<service>
       <type>_nfs._tcp</type>
       <port>2049</port>
       <txt-record>path=/srv/video/Filme</txt-record> ## path to shared Folder
       <txt-record>subtype=video</txt-record> ## subtype
       <txt-record>category=movies</txt-record> ## category
</service>
</service-group>
```

