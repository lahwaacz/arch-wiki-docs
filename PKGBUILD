# Maintainer: Jakub Klinkovský <j.l.k@gmx.com>

_pkgname=arch-wiki-docs
pkgname=arch-wiki-docs-clean
pkgdesc="Pages from Arch Wiki optimized for offline browsing"
pkgver=2014.03.10
pkgrel=1
arch=('any')
url="https://github.com/lahwaacz/arch-wiki-docs"
license=('FDL')
options=('!strip')
# dump_html does not require running the script, the pages are already processed
#makedepends=('git' 'python' 'python-simplemediawiki-git')
makedepends=('git')
source=('git://github.com/lahwaacz/arch-wiki-docs.git#branch=dump_html')
md5sums=('SKIP')

pkgver() {
  cd "$_pkgname"
  git log -1 --format=%ci | cut -d ' ' -f 1 | sed 's|-|.|g'
}

build() {
  cd "$_pkgname"
# dump_html does not require running the script, the pages are already processed
#  python arch-wiki-docs.py
}

package() {
  cd "$_pkgname"
  install -dm755 "$pkgdir/usr/share/doc/arch-wiki/html-clean"
  cp -r wiki/* "$pkgdir/usr/share/doc/arch-wiki/html-clean/"
}

# vim:set ts=2 sw=2 et:
