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
depends=('python2-gobject2' 'python2-dbus' "python2-gobject" 'autofs' 'avahi')
provides=('$pkgname')
backup=("etc/avahi-linker/default.cfg")
source=("avahi-linker.py"
        "default.cfg"
        "avahi-linker.service"
        "i18n.tar.gz")
md5sums=('96408e45353c5393d78bd439030f89e8'
         'd4ab1543752a53c00dd9e496e527bddb'
         '3c9a120902fe9eeda050c5dd313de6b9'
         '074fd81bd683bc88efc9e5ce468db902')


package() {
  install -Dm755 avahi-linker.py "$pkgdir/usr/bin/avahi-linker"
  install -D -m644 default.cfg  "$pkgdir/etc/avahi-linker/default.cfg"
  install -D -m644 "${srcdir}"/avahi-linker.service "${pkgdir}"/usr/lib/systemd/system/avahi-linker.service
  cd $srcdir/i18n
  make DESTDIR=$pkgdir i18n
}

# vim:set ts=2 sw=2 et:
