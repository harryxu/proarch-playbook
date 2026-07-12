#!/bin/bash

BG_DIR="/usr/share/sddm/themes/silent/backgrounds/random-backgrounds"
TARGET="/usr/share/sddm/themes/silent/backgrounds/random.jpg"

# Do nothing if the directory doesn't exist or contains no image files
if [ ! -d "$BG_DIR" ]; then
    exit 0
fi

mapfile -t images < <(find "$BG_DIR" -maxdepth 1 -type f \( \
    -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o \
    -iname "*.webp" -o -iname "*.bmp" \) 2>/dev/null)

if [ "${#images[@]}" -eq 0 ]; then
    exit 0
fi

# Pick a random image
selected="${images[RANDOM % ${#images[@]}]}"

# Create/overwrite symlink (force, even if target is a regular file)
ln -sf "$selected" "$TARGET"
