#!/bin/bash

# Check MAKEPKG_DIR
echo "MAKEPKG_DIR=$MAKEPKG_DIR"

# Get the package repo
git clone ssh://aur@aur.archlinux.org/i3expo.git aur
cd aur

# Create SRC info
/bin/bash "$MAKEPKG_DIR/makepkg" --config="$config" --printsrcinfo
