#!/bin/bash

set -ex
cd "$TRAVIS_BUILD_DIR/package"

# Get the repo
git clone ssh://aur@aur.archlinux.org/i3expo.git aur

# Update it
cp PKGBUILD aur
cd aur
/bin/bash "$MAKEPKG_DIR/makepkg" --config="$config" --printsrcinfo > .SRCINFO

# Commit
git add PKGBUILD .SRCINFO
git config user.email "deploy@mihalea.ro"
git config user.name "mihalea-deploy"
git commit -m "Release $TRAVIS_TAG"

# Deploy to AUR
git push origin master
