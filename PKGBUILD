# Maintainer Mircea Mihalea <mircea at mihalea dot ro>

pkgname=i3expo-git
pkgver=1.0.1
pkgrel=1
pkgdesc="Provide a workspace overview for i3wm"
url="https://github.com/mihalea/i3expo"
depends=('python' 'python-i3ipc' 'python-pillow-simd' 'python-timing' 'python-pyxdg' 'python-pygame')
makedepends=('gcc' 'python-setuptools')
license=('MIT')
arch=('any')
provides=('i3expod' 'i3expo')
source=("git+https://github.com/mihalea/i3expo.git#branch=deps")
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
		install -D -m 0644 "prtscn.so" "$pkgdir/usr/share/i3expo/prtscn.so"
		install -D -m 0644 "prtscn.c" "$pkgdir/usr/share/i3expo/prtscn.c"
		install -D -m 0644 "LICENSE" "$pkgdir/usr/share/licenses/i3expo/LICENSE"
}
