#!/bin/bash

# Define colors for better readability
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to test a JONQ query
test_query() {
    local test_name="$1"
    local json_file="$2"
    local query="$3"
    
    echo -e "${BLUE}===== TESTING: ${test_name} =====${NC}"
    echo -e "${YELLOW}QUERY:${NC} jonq $json_file \"$query\""
    
    output=$(jonq "$json_file" "$query" 2>&1)
    status=$?
    
    if [ $status -eq 0 ] && ! [[ "$output" == *"Error"* ]]; then
        echo -e "${GREEN}PASS${NC}"
        echo "Output preview:"
        echo "$output" | head -n 5
        if [ $(echo "$output" | wc -l) -gt 5 ]; then
            echo "..."
        fi
        return 0
    else
        echo -e "${RED}FAIL${NC}"
        echo "Error details:"
        echo "$output"
        return 1
    fi
}

# Run the tests
echo "====== JONQ FIXES TEST SUITE ======"

# Test 1: Simple query
test_query "Simple selection" "json_test_files/simple.json" "select name, age"

# Test 2: Query with HAVING clause
test_query "HAVING clause" "json_test_files/simple.json" "select city, avg(age) as avg_age, count(*) as count group by city having avg_age > 25"

# Test 3: Arithmetic operation
test_query "Arithmetic" "json_test_files/simple.json" "select max(age) - min(age) as age_range"

# Test 4: BETWEEN operator
test_query "BETWEEN operator" "json_test_files/nested.json" "select order_id, item, price from [].orders if price between 700 and 1000"

# Test 5: CONTAINS operator
test_query "CONTAINS operator" "json_test_files/nested.json" "select order_id, item from [].orders if item contains 'a'"

# Test 6: Array handling
test_query "Array handling" "json_test_files/nested.json" "select name, count(orders) as order_count"

echo "====== TEST SUMMARY ======"