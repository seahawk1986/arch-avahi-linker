# Maintainer: Alexander Grothe <seahawk1986[at]hotmail.com>
pkgname=avahi-linker
pkgver=0.0.1
pkgrel=1
epoch=
pkgdesc="link autofs nfs automounts using remote avahi service announcements"
arch=('x86_64')
url=""
license=('GPL2')
groups=()
depends=('python2-gobject2' 'python2-dbus' "python2-gobject" 'autofs')
provides=('$pkgname')
backup=("etc/avahi-linker/default.cfg")
source=("avahi-linker.py"
        "default.cfg"
        "avahi-linker.service")
md5sums=('81274930b384ed3aeb2281392ec825ed'
         '4ea2fea73769232361478cc504922fe3'
         '5d44dc2066a225e0f09faf7fdaef85d1')

package() {
  install -Dm755 avahi-linker.py "$pkgdir/usr/bin/avahi-linker"
  install -D -m644 default.cfg  "$pkgdir/etc/avahi-linker/default.cfg"
  install -D -m644 "${srcdir}"/avahi-linker.service "${pkgdir}"/usr/lib/systemd/system/avahi-linker.service
}

# vim:set ts=2 sw=2 et:
