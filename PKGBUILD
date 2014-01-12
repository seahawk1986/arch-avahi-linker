# Maintainer: Alexander Grothe <seahawk1986[at]hotmail.com>
pkgname=avahi-linker
pkgver=0.0.2
pkgrel=1
epoch=
pkgdesc="link autofs nfs automounts using remote avahi service announcements"
arch=('x86_64')
url=""
license=('GPL3')
groups=()
depends=('python2-gobject2' 'python2-dbus' "python2-gobject" "python2-ipaddr" 'autofs' 'avahi')
provides=('$pkgname')
backup=("etc/avahi-linker/default.cfg")
source=("avahi-linker.py"
        "default.cfg"
        "avahi-linker.service"
        "vdr-update-monitor.service"
        "vdr-net-monitor.service"
        "net_monitor.py"
        "update_monitor.py"
        "i18n.tar.gz")
md5sums=('6285ffcf5d77e7a5285dad4117147f50'
         '6c410ca8e5083543a67d33ae2532a050'
         'bf8ecf1afe546e5df0eb2126da6b90ef'
         'a829a83981680b659bfeb47e2af4454b'
         '22311f85260b3a8460d518f0c8673b0f'
         '6acbb4b206fe9e346e609530c5b1af17'
         '2c8d238a47cd31439b673433f0195524'
         '074fd81bd683bc88efc9e5ce468db902')


package() {
  install -Dm755 avahi-linker.py "$pkgdir/usr/bin/avahi-linker"
  install -Dm755 net_monitor.py "$pkgdir/usr/bin/vdr-net-monitor"
  install -Dm755 update_monitor.py "$pkgdir/usr/bin/vdr-update-monitor"
  install -D -m644 default.cfg  "$pkgdir/etc/avahi-linker/default.cfg"
  install -D -m644 "${srcdir}/avahi-linker.service" "${pkgdir}/usr/lib/systemd/system/avahi-linker.service"
  install -D -m644 "${srcdir}/vdr-update-monitor.service"  "${pkgdir}/usr/lib/systemd/system/vdr-update-monitor.service"
  install -D -m644 "${srcdir}/vdr-net-monitor.service"  "${pkgdir}/usr/lib/systemd/system/vdr-net-monitor.service"
  cd $srcdir/i18n
  make DESTDIR=$pkgdir i18n
}

# vim:set ts=2 sw=2 et:
