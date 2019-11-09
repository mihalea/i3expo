# Maintainer Mircea Mihalea <mircea at mihalea dot ro>

pkgname=i3expo
_module='i3expo'
pkgver=0.4
pkgrel=1
pkgdesc="Provide a workspace overview for i3wm"
url="https://github.com/mihalea/i3expo"
depends=('python' 'python-i3ipc')
builddepends=('gcc')
license=('MIT')
arch=('any')
provides=('i3expo')
source=("git+https://github.com/mihalea/i3expo.git")
md5sums=('SKIP')

build() {
    cd "${pkgname}"
    python setup.py build
}

package() {
    depends+=()
    cd "${pkgname}"
    python setup.py install --root="${pkgdir}" --optimize=1 --skip-build
    install -D -m 0644 "defaultconfig" "$pkgdir/usr/share/i3expo/config.example"
}
