#!/bin/bash

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

JSON_PATH="/Users/oha/jonq/tests/json_test_files"

# Initialize counters
total_tests=0
passed_tests=0
failed_tests=0

run_command() {
  echo -e "\n-----------------------------------------"
  echo -e "${YELLOW}RUNNING:${NC} $1"
  echo "-----------------------------------------"
  
  output=$(eval $1 2>&1)
  exit_status=$?
  
  total_tests=$((total_tests + 1))
  
  if [ $exit_status -ne 0 ] || [[ "$output" == *"Error"* ]]; then
    echo -e "${RED}ERROR:${NC}"
    echo -e "${RED}$output${NC}"
    failed_tests=$((failed_tests + 1))
  else
    echo -e "${GREEN}SUCCESS${NC}"
    echo "$output" | head -n 10
    if [ $(echo "$output" | wc -l) -gt 10 ]; then
      echo "..."
    fi
    passed_tests=$((passed_tests + 1))
  fi
  echo
}

# Print test summary
print_summary() {
  echo -e "\n====================================================="
  echo -e "${BLUE}TEST SUMMARY${NC}"
  echo -e "====================================================="
  echo -e "Total tests: $total_tests"
  echo -e "${GREEN}Passed tests: $passed_tests${NC}"
  echo -e "${RED}Failed tests: $failed_tests${NC}"
  
  # Calculate pass percentage
  if [ $total_tests -gt 0 ]; then
    pass_percentage=$(echo "scale=1; $passed_tests * 100 / $total_tests" | bc)
    echo -e "Success rate: ${pass_percentage}%"
  fi
  echo -e "====================================================="
}

# SIMPLE JSON TESTS
simple_json_tests=(
  "jonq $JSON_PATH/simple.json \"select *\""
  "jonq $JSON_PATH/simple.json \"select name, age\""
  "jonq $JSON_PATH/simple.json \"select name, age if age > 30\""
  "jonq $JSON_PATH/simple.json \"select name, age sort age desc 2\""
  "jonq $JSON_PATH/simple.json \"select sum(age) as total_age\""
  "jonq $JSON_PATH/simple.json \"select avg(age) as average_age\""
  "jonq $JSON_PATH/simple.json \"select count(age) as count_age\""
  "jonq $JSON_PATH/simple.json \"select min(age) as youngest, max(age) as oldest\""
  "jonq $JSON_PATH/simple.json \"select city, count(*) as count group by city\""
  "jonq $JSON_PATH/simple.json \"select city, avg(age) as avg_age group by city\""
  "jonq $JSON_PATH/simple.json \"select city, count(*) as count group by city having count >= 1\""
)

# NESTED JSON TESTS
nested_json_tests=(
  "jonq $JSON_PATH/nested.json \"select name, profile.age\""
  "jonq $JSON_PATH/nested.json \"select name, profile.address.city\""
  "jonq $JSON_PATH/nested.json \"select name, count(orders) as order_count\""
  "jonq $JSON_PATH/nested.json \"select name, orders[0].item as first_item\""
  "jonq $JSON_PATH/nested.json \"select name if orders[0].price > 1000\""
  "jonq $JSON_PATH/nested.json \"select profile.address.city, avg(profile.age) as avg_age group by profile.address.city\""
  "jonq $JSON_PATH/nested.json \"select profile.address.city, avg(profile.age) as avg_age group by profile.address.city having avg_age > 25\""
  "jonq $JSON_PATH/nested.json \"select order_id, item, price from [].orders\""
  "jonq $JSON_PATH/nested.json \"select order_id, item, price from [].orders if price > 800\""
)

# COMPLEX JSON TESTS
complex_json_tests=(
  "jonq $JSON_PATH/complex.json \"select company.name, company.headquarters.city\""
  "jonq $JSON_PATH/complex.json \"select name, founded from company.subsidiaries[] if founded > 2008\""
  "jonq $JSON_PATH/complex.json \"select avg(products[].versions[].pricing.monthly) as avg_price\""
  "jonq $JSON_PATH/complex.json \"select sum(company.subsidiaries[].financials.profit) as total_profit\""
  "jonq $JSON_PATH/complex.json \"select name, avg(versions[].pricing.monthly) as avg_monthly_price from products[]\""
)

echo "====================================================="
echo "SIMPLE JSON TESTS"
echo "====================================================="

for cmd in "${simple_json_tests[@]}"; do
  run_command "$cmd"
done

echo -e "\n====================================================="
echo "COMPLEX JSON TESTS"
echo "====================================================="

for cmd in "${complex_json_tests[@]}"; do
  run_command "$cmd"
done

echo -e "\n====================================================="
echo "NESTED JSON TESTS"
echo "====================================================="

for cmd in "${nested_json_tests[@]}"; do
  run_command "$cmd"
done

# Print final test summary
print_summary

echo "-----------------------------------------"
echo "Test script completed"
echo "-----------------------------------------"