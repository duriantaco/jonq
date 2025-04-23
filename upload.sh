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

log "Cleaning previous builds..."
rm -rf dist build jonq.egg-info jonq_fast/target/wheels/*.whl
mkdir -p dist

log "Building packages separately..."

log "Building Rust extension (jonq_fast)..."
cd jonq_fast
maturin build --release || error "Failed to build Rust extension"
cp target/wheels/*.whl ../dist/
cd ..

log "Building Python package (jonq)..."
python -m build || error "Failed to build Python package"

log "Built packages:"
ls -lh dist/

log "Testing packages..."
pip install --force-reinstall dist/jonq*.whl dist/jonq_fast*.whl
python -c "from jonq.csv_utils import flatten_json; import jonq_fast; print('Both packages loaded successfully')" || warn "Test failed"

success "Build successful!"

mkdir -p dist/jonq dist/jonq_fast
cp dist/jonq-*.whl dist/jonq/
cp dist/jonq_fast-*.whl dist/jonq_fast/

echo ""
echo "===================================================================="
echo "IMPORTANT: You need to upload both packages to PyPI separately"
echo "===================================================================="
echo ""
echo "1. Upload jonq (Python package):"
echo "   twine upload dist/jonq/jonq-*.whl"
echo ""
echo "2. Upload jonq_fast (Rust extension):"
echo "   twine upload dist/jonq_fast/jonq_fast-*.whl"
echo ""
echo "To install locally:"
echo "   pip install dist/jonq/jonq-*.whl dist/jonq_fast/jonq_fast-*.whl"
echo ""
echo "Users will need to install both packages:"
echo "   pip install jonq jonq-fast"
echo ""