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

log "Checking environment..."
if ! command -v jq &> /dev/null; then
    warn "jq is not installed. This is required for the final package to work."
    warn "Install jq before using jonq: https://stedolan.github.io/jq/download/"
fi

log "Installing build dependencies..."
pip install -U pip maturin hatchling twine wheel build

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

log "Testing Rust extension..."
pip install --force-reinstall dist/jonq_fast*.whl
python -c "import jonq_fast; print('Rust extension test:', jonq_fast.flatten({'test': 'data'}, '.'))" || error "Rust extension test failed"

log "Testing Python package..."
pip install --force-reinstall dist/jonq*.whl
python -c "from jonq.csv_utils import flatten_json; print('Python package test:', flatten_json({'test': 'data'}))" || error "Python package test failed"

success "Build successful!"
echo ""
echo "Packages are built as separate wheels, which is the correct approach."
echo "The packages are designed to work together but remain separate."
echo ""
echo "To upload to PyPI (separate packages):"
echo "  twine upload dist/*.whl"
echo ""
echo "To install locally:"
echo "  pip install dist/jonq-*.whl                 # Python package only"
echo "  pip install dist/jonq_fast-*.whl            # Rust extension only"
echo "  pip install dist/jonq-*.whl dist/jonq_fast-*.whl  # Both packages"
echo ""