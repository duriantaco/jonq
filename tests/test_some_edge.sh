#!/bin/bash

# Colors for better visibility
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

run_test() {
  local command="$1"

  echo -e "${BLUE}===== Testing: $command =====${NC}"
  
  # Execute the command
  eval "$command" > /tmp/jonq_output 2>&1
  status=$?
  
  # Check the output
  if [ $status -eq 0 ] && [ -s /tmp/jonq_output ]; then
    echo -e "${GREEN}PASS${NC}"
    echo "Output preview:"
    head -n 5 /tmp/jonq_output
  else
    echo -e "${RED}FAIL${NC}"
    echo "Error details:"
    cat /tmp/jonq_output
  fi
  echo "----------------------------------------"
}

echo "=== TESTING HAVING CLAUSE FIX ==="
run_test "jonq json_test_files/simple.json \"select city, avg(age) as avg_age, count(*) as count group by city having avg_age > 25 and count > 0\""

echo "=== TESTING ARITHMETIC OPERATIONS FIX ==="
run_test "jonq json_test_files/simple.json \"select max(age) - min(age) as age_range\""

echo "=== TESTING BETWEEN OPERATOR FIX ==="
run_test "jonq json_test_files/nested.json \"select order_id, item, price from [].orders if price between 700 and 1000\""

echo "=== TESTING CONTAINS OPERATOR FIX ==="
run_test "jonq json_test_files/nested.json \"select order_id, item, price from [].orders if item contains 'a'\""

echo "=== TESTING NESTED ARRAY HANDLING FIX ==="
run_test "jonq json_test_files/nested.json \"select profile.address.city, count(orders[]) as total_orders, avg(orders[].price) as avg_price group by profile.address.city\""

echo "=== TESTING COMPLEX ARRAY ACCESS FIX ==="
run_test "jonq json_test_files/complex.json \"select products[].versions[].version, products[].versions[].pricing.monthly\""

echo "=== TESTING GROUPING WITH ARRAY FIX ==="
run_test "jonq json_test_files/complex.json \"select type, avg(versions[].pricing.monthly) as avg_price group by type from products[]\""

echo "=== TESTING COMPLEX HAVING CONDITION FIX ==="
run_test "jonq json_test_files/complex.json \"select type, avg(versions[].pricing.monthly) as avg_monthly, count(*) as count group by type having avg_monthly > 200 and count > 0 from products[]\""

echo "=== TEST COMPLETE ==="