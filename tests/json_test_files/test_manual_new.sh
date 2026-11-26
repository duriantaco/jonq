#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color
source_file="$(cd -- "$(dirname -- "$0")" && pwd)/all.json"

# Test counter
TOTAL_TESTS=0
PASSED_TESTS=0

# Function to run a test
run_test() {
    local test_name="$1"
    local query="$2"
    local expected="$3"
    
    echo -e "${YELLOW}Running: $test_name${NC}"
    echo "Query: $query"
    
    # Run the command and capture output
    actual=$(jonq "$source_file" "$query" 2>&1)
    exit_code=$?
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    
    if [ $exit_code -ne 0 ]; then
        echo -e "${RED}FAIL - Command failed with exit code $exit_code${NC}"
        echo "Error output: $actual"
        echo
        return
    fi
    
    if jq -es --argjson expected "$expected" '. == [$expected]' <<<"$actual" >/dev/null; then
        echo -e "${GREEN}PASS${NC}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo -e "${RED}FAIL - Output mismatch${NC}"
        echo "Expected: $expected"
        echo "Actual:   $actual"
    fi
    echo
}

echo "=== JONQ Test Suite ==="
echo

# Test 1: All rows
run_test "All rows" \
    "select * from []" \
    "$(cat "$source_file")"

# Test 2: Project a couple of fields  
run_test "Project fields" \
    "select id, name from []" \
    '[{"id":1,"name":"alpha"},{"id":2,"name":"beta"},{"id":3,"name":"alphabet"},{"id":4,"name":"gamma"}]'

# Test 3: Nested array projection
run_test "Nested array projection" \
    "select price from [].items where price is not null" \
    '[{"price":10},{"price":-350}]'

# Test 4: WHERE with parens precedence
run_test "WHERE with parens precedence" \
    "select id from [] if a > 1 and (b < 2 or c > 6)" \
    '[{"id":1},{"id":3}]'

# Test 5: Float/scientific literal on nested field
run_test "Scientific notation comparison" \
    "select price from [].items if price > -3.5e2" \
    '[{"price":10}]'

# Test 6: Negative compare
run_test "Negative comparison" \
    "select id from [] if c < 0" \
    '[{"id":4}]'

# Test 7: Case-sensitive contains
run_test "Case-sensitive contains" \
    "select name from [] if name contains \"alpha\"" \
    '[{"name":"alpha"},{"name":"alphabet"}]'

# Test 8: Contains against a string
run_test "Contains in text field" \
    "select id from [] if text contains \"Bar\"" \
    '[{"id":1}]'

# Test 9: Between clause
run_test "Between clause" \
    "select id from [] if c between 5 and 8" \
    '[{"id":2}]'

# Summary
echo "=== Test Results ==="
echo "Passed: $PASSED_TESTS/$TOTAL_TESTS"

if [ $PASSED_TESTS -eq $TOTAL_TESTS ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed.${NC}"
    exit 1
fi
