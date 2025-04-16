#!/bin/bash

echo "=== JONQ EDGE CASES TEST ==="
echo "Testing boundary conditions and error handling"
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
    result="FAIL: $(echo "$output" | head -n 1)"
  fi

  if [ "$result" = "$expected_result" ] || ([[ "$result" =~ ^FAIL ]] && [ "$expected_result" = "FAIL" ]); then
    echo "RESULT: $result (Expected)"
  else
    echo "RESULT: $result (Unexpected - Expected $expected_result)"
  fi
  echo "----------------------------------------"
}

echo "=== MISSING DATA HANDLING ==="
run_test "Accessing non-existent array index" 'jonq json_test_files/nested.json "select name, orders[5].item"'
run_test "Accessing non-existent nested field" 'jonq json_test_files/nested.json "select name, profile.nonexistent.field"'
run_test "Filtering on non-existent field" 'jonq json_test_files/nested.json "select name if nonexistent > 10"' "FAIL"
run_test "Aggregation on empty array" 'jonq json_test_files/nested.json "select name, count(nonexistent) as count"'

echo "=== BOUNDARY VALUES ==="
run_test "Equal to boundary" 'jonq json_test_files/nested.json "select name, profile.age if profile.age == 25"' "FAIL" # Expected to fail with exact numeric comparison
run_test "Zero value comparison" 'jonq json_test_files/nested.json "select name, profile.age if profile.age > 0"'
run_test "Selecting many fields" 'jonq json_test_files/nested.json "select id, name, profile.age, profile.address.city, profile.address.zip, orders[0].item, orders[0].price"' 
run_test "Very large numbers" 'jonq json_test_files/complex.json "select name, financials.revenue from company.subsidiaries[] if financials.revenue > 10000000"'

echo "=== SYNTAX EDGE CASES ==="
run_test "No spaces in query" 'jonq json_test_files/nested.json "select name,profile.age"'
run_test "Extra spaces in query" 'jonq json_test_files/nested.json "select  name ,  profile.age  "'
run_test "Case sensitivity in fields" 'jonq json_test_files/nested.json "select NAME, Profile.Age"' "FAIL" # Expected to fail due to case sensitivity
run_test "Complex field path with multiple arrays" 'jonq json_test_files/complex.json "select products[0].versions[0].pricing.monthly"'

echo "=== ALIASING AND RENAMING ==="
run_test "Simple aliasing" 'jonq json_test_files/nested.json "select name as customer_name, profile.age as customer_age"'
run_test "Aliasing with spaces" 'jonq json_test_files/nested.json "select name as \"Customer Name\""' "FAIL" # Expected to fail with quoted alias
run_test "Aliasing without as keyword" 'jonq json_test_files/nested.json "select name customer_name"' "FAIL" # Expected to fail without 'as'

echo "=== COMBINATION QUERIES ==="
run_test "Filter + sort + limit" 'jonq json_test_files/nested.json "select name, profile.age if profile.age > 20 sort profile.age 1"'
run_test "Aggregation + sort" 'jonq json_test_files/nested.json "select name, count(orders) as order_count sort order_count"'
run_test "Multiple aggregations" 'jonq json_test_files/nested.json "select count(orders) as order_count, avg(profile.age) as avg_age"'

echo "=== ERROR HANDLING ==="
run_test "Invalid syntax - missing select" 'jonq json_test_files/nested.json "name, age"' "FAIL"
run_test "Invalid syntax - missing comma" 'jonq json_test_files/nested.json "select name profile.age"' "FAIL"
run_test "Invalid syntax - invalid aggregation" 'jonq json_test_files/nested.json "select invalid(profile.age)"' "FAIL"
run_test "Invalid file path" 'jonq nonexistent.json "select *"' "FAIL"

echo "=== SPECIAL QUERY TYPES ==="
run_test "Select with only aggregation" 'jonq json_test_files/nested.json "select count(*) as count"'
run_test "Empty result filtering" 'jonq json_test_files/nested.json "select name if profile.age > 100"'
run_test "Group by with having clause" 'jonq json_test_files/nested.json "select profile.address.city, avg(profile.age) as avg_age group by profile.address.city having avg_age > 20"'

echo "=== TEST COMPLETE ==="