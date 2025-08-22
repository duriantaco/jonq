#!/bin/bash
set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }


log "Building packages separately..."

log "Building Python package (jonq)..."
python -m build || error "Failed to build Python package"

log "Built packages:"
ls -lh dist/

success "Build successful!"


echo ""
echo "===================================================================="
echo "IMPORTANT: You need to upload both packages to PyPI separately"
echo "===================================================================="
echo ""
echo "1. Upload jonq (Python package):"
echo "   twine upload dist/jonq/jonq-*.whl"
echo ""