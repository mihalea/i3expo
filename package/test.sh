#!/bin/bash

# Get the package repo
git clone ssh://aur@aur.archlinux.org/i3expo.git aur
cd aur

/bin/bash "$MAKEPKG_DIR/makepkg" --config="$config" --printsrcinfo
