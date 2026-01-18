#!/bin/bash
# Compress/decompress data files for git storage

set -e

DATA_DIR="data"
RAW_DIR="$DATA_DIR/raw"
PROCESSED_DIR="$DATA_DIR/processed"

compress() {
    echo "Compressing data files..."

    # Compress PDFs
    find "$RAW_DIR" -name "*.pdf" -exec gzip -k {} \;

    # Compress processed markdown
    find "$PROCESSED_DIR" -name "*.md" -exec gzip -k {} \;
    find "$PROCESSED_DIR" -name "*.json" -exec gzip -k {} \;

    echo "Done. Remove originals with: $0 clean"
}

decompress() {
    echo "Decompressing data files..."

    # Decompress all .gz files
    find "$DATA_DIR" -name "*.gz" -exec gunzip -k {} \;

    echo "Done."
}

clean() {
    echo "Removing uncompressed files (keeping .gz)..."

    # Remove uncompressed files where .gz exists
    find "$RAW_DIR" -name "*.pdf" -exec rm {} \;
    find "$PROCESSED_DIR" -name "*.md" ! -name "*.gz" -exec rm {} \;
    find "$PROCESSED_DIR" -name "*.json" ! -name "*.gz" -exec rm {} \;

    echo "Done."
}

clean_gz() {
    echo "Removing .gz files (keeping originals)..."
    find "$DATA_DIR" -name "*.gz" -exec rm {} \;
    echo "Done."
}

case "${1:-}" in
    compress) compress ;;
    decompress) decompress ;;
    clean) clean ;;
    clean-gz) clean_gz ;;
    *)
        echo "Usage: $0 {compress|decompress|clean|clean-gz}"
        echo ""
        echo "  compress    - Create .gz files (keeps originals)"
        echo "  decompress  - Extract .gz files (keeps .gz)"
        echo "  clean       - Remove originals, keep .gz only"
        echo "  clean-gz    - Remove .gz files, keep originals"
        exit 1
        ;;
esac
