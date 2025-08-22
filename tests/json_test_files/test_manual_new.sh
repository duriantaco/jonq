#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
TOTAL_TESTS=0
PASSED_TESTS=0

# Function to run a test
run_test() {
    local test_name="$1"
    local command="$2" 
    local expected="$3"
    
    echo -e "${YELLOW}Running: $test_name${NC}"
    echo "Command: $command"
    
    # Run the command and capture output
    actual=$(eval "$command" 2>&1)
    exit_code=$?
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    
    if [ $exit_code -ne 0 ]; then
        echo -e "${RED}FAIL - Command failed with exit code $exit_code${NC}"
        echo "Error output: $actual"
        echo
        return
    fi
    
    # Compare outputs (normalize whitespace)
    actual_normalized=$(echo "$actual" | tr -d ' \n\t')
    expected_normalized=$(echo "$expected" | tr -d ' \n\t')
    
    if [ "$actual_normalized" = "$expected_normalized" ]; then
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
    "jonq /Users/oha/jonq/tests/json_test_files/all.json 'select * from []'" \
    '[{"id":1,"name":"alpha","a":2,"b":1,"c":7,"text":"Foo Bar","items":[{"name":"item1","price":10}]},{"id":2,"name":"beta","a":3,"b":1,"c":6,"text":"hello world","items":[{"name":"item2","price":-350}]},{"id":3,"name":"alphabet","a":4,"b":5,"c":9,"text":"ALPHA beta","items":[]},{"id":4,"name":"gamma","a":1,"b":3,"c":-2,"text":"bar","items":[]}]'

# Test 2: Project a couple of fields  
run_test "Project fields" \
    "jonq /Users/oha/jonq/tests/json_test_files/all.json 'select id, name from []'" \
    '[{"id":1,"name":"alpha"},{"id":2,"name":"beta"},{"id":3,"name":"alphabet"},{"id":4,"name":"gamma"}]'

# Test 3: Nested array projection
run_test "Nested array projection" \
    "jonq /Users/oha/jonq/tests/json_test_files/all.json 'select items[].price from []'" \
    '[10,-350]'

# Test 4: WHERE with parens precedence
run_test "WHERE with parens precedence" \
    "jonq /Users/oha/jonq/tests/json_test_files/all.json 'select id from [] if a > 1 and (b < 2 or c > 6)'" \
    '[1,3]'

# Test 5: Float/scientific literal on nested field
run_test "Scientific notation comparison" \
    "jonq /Users/oha/jonq/tests/json_test_files/all.json 'select items[].price from [] if items[].price > -3.5e2'" \
    '[10]'

# Test 6: Negative compare
run_test "Negative comparison" \
    "jonq /Users/oha/jonq/tests/json_test_files/all.json 'select id from [] if c < 0'" \
    '[4]'

# Test 7: Case-sensitive contains
run_test "Case-sensitive contains" \
    "jonq /Users/oha/jonq/tests/json_test_files/all.json 'select name from [] if name contains \"alpha\"'" \
    '[\"alpha\",\"alphabet\"]'

# Test 8: Contains against another field
run_test "Contains with field matching" \
    "jonq /Users/oha/jonq/tests/json_test_files/all.json 'select id from [] if text contains \"Bar\"'" \
    '[1]'

# Test 9: Between clause
run_test "Between clause" \
    "jonq /Users/oha/jonq/tests/json_test_files/all.json 'select id from [] if c between 5 and 8'" \
    '[2]'

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