#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

echo ""

# Decrypt private key
openssl aes-256-cbc -K $encrypted_3166097aa039_key -iv $encrypted_3166097aa039_iv
    -in package/private_key.enc -out /tmp/private_key -d
chmod 600 /tmp/deploy_key
echo "Decrypted and permissioned the deployment key"

# Set up to run makepkg
wget https://www.archlinux.org/packages/core/x86_64/pacman/download/ -O pacman.pkg.tar.xz
tar -Jxf pacman.pkg.tar.xz
export MAKEPKG_DIR="$(pwd)/usr/bin"
export PATH="$MAKEPKG_DIR:$PATH"
export LIBRARY="$(pwd)/usr/share/makepkg"
config="$(pwd)/etc/makepkg.conf"
echo "Installed makepkg"

# Set up git to use the private key and skip host checking
git config --global --add core.sshCommand "ssh -o StrictHostKeyChecking=false -i /tmp/private_key"