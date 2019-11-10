# Maintainer Mircea Mihalea <mircea at mihalea dot ro>

pkgname=i3expo-git
_module='i3expo'
pkgver=0.4
pkgrel=1
pkgdesc="Provide a workspace overview for i3wm"
url="https://github.com/mihalea/i3expo"
depends=('python')
builddepends=('gcc python-setuptools')
license=('MIT')
arch=('any')
provides=('i3expo')
source=("git+https://github.com/mihalea/i3expo.git")
md5sums=('SKIP')

build() {
    cd "i3expo"
		gcc -shared -O3 -Wall -fPIC -Wl,-soname,prtscn -o prtscn.so prtscn.c -lX11
    python setup.py build
}

package() {
    depends+=()
    cd "i3expo"
    python setup.py install --root="${pkgdir}" --optimize=1 --skip-build
    install -D -m 0644 "defaultconfig" "$pkgdir/usr/share/i3expo/config.example"
		install -D -m 0644 "prtscn.so" "$pkgdir/usr/share/i3expo/prtscn.so"
		install -D -m 0644 "prtscn.c" "$pkgdir/usr/share/i3expo/prtscn.c"
}
