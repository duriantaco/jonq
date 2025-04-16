#!/bin/bash

echo "=== Testing simple.json queries ==="
echo

run_test() {
  local description=$1
  local command=$2

  echo "Test: $description"
  echo "Command: $command"
  
  output=$(eval "$command" 2>&1)
  status=$?
  
  if [ $status -eq 0 ] && [ -n "$output" ]; then
    echo "PASS"
  else
    echo "FAIL: $(echo $output | head -n 1)"
  fi
  echo "----------------------------------------"
}

run_test "Select all fields" 'jonq json_test_files/simple.json "select *"'
run_test "Select specific fields" 'jonq json_test_files/simple.json "select name, age"'
run_test "Basic filtering" 'jonq json_test_files/simple.json "select name, age if age > 30"'
run_test "Sort descending with limit" 'jonq json_test_files/simple.json "select name, age sort age desc 2"'
run_test "Sum aggregation" 'jonq json_test_files/simple.json "select sum(age) as total_age"'
run_test "Average aggregation" 'jonq json_test_files/simple.json "select avg(age) as total_age"'
run_test "Count aggregation" 'jonq json_test_files/simple.json "select count(age) as total_age"'
run_test "Min/Max aggregation" 'jonq json_test_files/simple.json "select min(age) as youngest, max(age) as oldest"'
run_test "Group by single field" 'jonq json_test_files/simple.json "select city, count(*) as count group by city"'
run_test "Group by with aggregation" 'jonq json_test_files/simple.json "select city, avg(age) as avg_age group by city"'
run_test "Group by with HAVING clause" 'jonq json_test_files/simple.json "select city, count(*) as count group by city having count >= 1"'

echo "=== Simple.json Tests Complete ==="