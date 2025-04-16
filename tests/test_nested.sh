#!/bin/bash

echo "=== JONQ CAPABILITIES TEST ==="
echo "Testing capabilities across complex nested structures"
echo

run_test() {
  local description=$1
  local command=$2
  local expected_result=${3:-"PASS"} 

  echo "Test: $description"
  echo "Command: $command"
  
  output=$(eval "$command" 2>&1)
  status=$?
  
  if [ $status -eq 0 ] && [ -n "$output" ]; then
    result="PASS"
  else
    result="FAIL: $(echo $output | head -n 1)"
  fi

  if [ "$result" == "$expected_result" ]; then
    echo "RESULT: $result (Expected)"
  else
    echo "RESULT: $result (Unexpected - Expected $expected_result)"
  fi
  echo "----------------------------------------"
}

echo "=== DEEP NESTING CAPABILITIES ==="
run_test "Deep field access (nested.json)" 'jonq json_test_files/nested.json "select name, profile.address.city, profile.address.zip"'
run_test "Deep field access (complex.json)" 'jonq json_test_files/complex.json "select company.headquarters.coordinates.latitude, company.headquarters.coordinates.longitude"'
run_test "Multiple nested levels (complex.json)" 'jonq json_test_files/complex.json "select company.name, company.headquarters.city, company.headquarters.country"'

echo "=== ARRAY INDEXING CAPABILITIES ==="
run_test "Array indexing (nested.json)" 'jonq json_test_files/nested.json "select name, orders[0].item, orders[0].price"'
run_test "Array indexing (complex.json)" 'jonq json_test_files/complex.json "select company.subsidiaries[0].name, company.subsidiaries[0].employees"'
run_test "Multiple array elements (nested.json)" 'jonq json_test_files/nested.json "select name, orders[0].price, orders[1].price"'
run_test "Multiple array elements (complex.json)" 'jonq json_test_files/complex.json "select products[0].name, products[1].name"'

echo "=== NUMERIC COMPARISON CAPABILITIES ==="
run_test "Greater than comparison (nested.json)" 'jonq json_test_files/nested.json "select name, profile.age if profile.age > 29"'
run_test "Less than comparison (nested.json)" 'jonq json_test_files/nested.json "select name, profile.age if profile.age < 26"'
run_test "Greater than comparison (complex.json)" 'jonq json_test_files/complex.json "select name, employees from company.subsidiaries[] if employees > 250"'
run_test "Multiple numeric conditions (nested.json)" 'jonq json_test_files/nested.json "select order_id, price from [].orders if price > 500 and price < 1000"'

echo "=== FROM CLAUSE CAPABILITIES ==="
run_test "Basic FROM clause (nested.json)" 'jonq json_test_files/nested.json "select order_id, item, price from [].orders"'
run_test "FROM with filter (nested.json)" 'jonq json_test_files/nested.json "select order_id, item, price from [].orders if price > 1000"'
run_test "FROM clause (complex.json)" 'jonq json_test_files/complex.json "select name, employees, financials.revenue from company.subsidiaries[]"'
run_test "FROM with nested arrays (complex.json)" 'jonq json_test_files/complex.json "select id, name, industry from products[].customers[]"'

echo "=== AGGREGATION CAPABILITIES ==="
run_test "Count aggregation (nested.json)" 'jonq json_test_files/nested.json "select name, count(orders) as order_count"'
run_test "Min aggregation (nested.json)" 'jonq json_test_files/nested.json "select min(orders[0].price) as min_first_order_price"'
run_test "Sum aggregation (complex.json)" 'jonq json_test_files/complex.json "select sum(company.subsidiaries[].employees) as total_employees"'
run_test "Avg aggregation (complex.json)" 'jonq json_test_files/complex.json "select avg(products[].versions[].pricing.monthly) as avg_price"'

echo "=== SORTING CAPABILITIES ==="
run_test "Basic sort (nested.json)" 'jonq json_test_files/nested.json "select name, profile.age sort profile.age"'
run_test "Sort descending (nested.json)" 'jonq json_test_files/nested.json "select name, profile.age sort profile.age desc"'
run_test "Sort with limit (nested.json)" 'jonq json_test_files/nested.json "select name, profile.age sort profile.age 1"'
run_test "Sort descending with limit (complex.json)" 'jonq json_test_files/complex.json "select name, employees, financials.revenue from company.subsidiaries[] sort financials.revenue desc 1"'

echo "=== GROUPING CAPABILITIES ==="
run_test "Group by with count (nested.json)" 'jonq json_test_files/nested.json "select profile.address.city, count(*) as user_count group by profile.address.city"'
run_test "Group by with avg (nested.json)" 'jonq json_test_files/nested.json "select profile.address.city, avg(profile.age) as avg_age group by profile.address.city"'
run_test "Group by with multiple aggregations (nested.json)" 'jonq json_test_files/nested.json "select profile.address.city, count(*) as user_count, avg(profile.age) as avg_age group by profile.address.city"'

echo "=== KNOWN LIMITATIONS ==="
# these tests are supposed to fail
run_test "String comparison (expected to fail)" 'jonq json_test_files/nested.json "select name if name == \"Alice\""' "FAIL"
run_test "Complex expressions (expected to fail)" 'jonq json_test_files/nested.json "select name if profile.age * 2 > 50"' "FAIL"
run_test "Function in condition (expected to fail)" 'jonq json_test_files/nested.json "select name if count(orders) > 1"' "FAIL"
run_test "Multi-field sorting (expected to fail)" 'jonq json_test_files/nested.json "select name, profile.age sort profile.age, profile.address.city"' "FAIL"
run_test "Having with different aggregate (expected to fail)" 'jonq json_test_files/nested.json "select profile.address.city, min(profile.age) as min_age group by profile.address.city having count(*) > 0"' "FAIL"

echo "=== TEST COMPLETE ==="