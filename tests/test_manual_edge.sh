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

# SIMPLE JSON EDGE CASES
simple_json_edge_cases=(
  "jonq $JSON_PATH/simple.json \"select city, age, count(*) as count group by city, age\""
  "jonq $JSON_PATH/simple.json \"select city, count(*) as count, sum(age) as total_age, avg(age) as avg_age, min(age) as min_age, max(age) as max_age group by city\""
  "jonq $JSON_PATH/simple.json \"select city, avg(age) as avg_age, count(*) as count group by city having avg_age > 25 and count > 0\""
  "jonq $JSON_PATH/simple.json \"select avg(age) + 10 as adjusted_avg\""
  "jonq $JSON_PATH/simple.json \"select max(age) - min(age) as age_range\""
  "jonq $JSON_PATH/simple.json \"select sum(age) / count(*) as manual_avg\""
  "jonq $JSON_PATH/simple.json \"select city, max(age) as max_age, min(age) as min_age group by city having max_age - min_age > 5\""
  "jonq $JSON_PATH/simple.json \"select city, avg(age) as avg_age group by city sort avg_age desc\""
)

# NESTED JSON EDGE CASES
nested_json_edge_cases=(
  "jonq $JSON_PATH/nested.json \"select profile.address.city, profile.address.zip, avg(profile.age) as avg_age group by profile.address.city, profile.address.zip\""
  "jonq $JSON_PATH/nested.json \"select profile.address.city, count(*) as count, avg(profile.age) as avg_age, min(profile.age) as min_age group by profile.address.city\""
  "jonq $JSON_PATH/nested.json \"select profile.address.city, count(orders[]) as total_orders, avg(orders[].price) as avg_price group by profile.address.city\""
  "jonq $JSON_PATH/nested.json \"select profile.address.city, sum(orders[].price) as total_spent group by profile.address.city having total_spent > 1000\""
  "jonq $JSON_PATH/nested.json \"select order_id, item, price from [].orders if price between 700 and 1000\""
  "jonq $JSON_PATH/nested.json \"select order_id, item, price from [].orders if item contains 'a'\""
  "jonq $JSON_PATH/nested.json \"select name, avg(orders[].price) / count(orders[]) as price_order_ratio\""
  "jonq $JSON_PATH/nested.json \"select name, min(orders[].price) as min_price, max(orders[].price) as max_price, avg(orders[].price) as avg_price\""
)

# COMPLEX JSON EDGE CASES
complex_json_edge_cases=(
  "jonq $JSON_PATH/complex.json \"select company.headquarters.coordinates.latitude, company.headquarters.coordinates.longitude\""
  "jonq $JSON_PATH/complex.json \"select products[0].versions[].version, products[0].versions[].pricing.monthly\""
  "jonq $JSON_PATH/complex.json \"select products[].versions[].version, products[].versions[].pricing.monthly\""
  "jonq $JSON_PATH/complex.json \"select company.subsidiaries[].headquarters.country, avg(company.subsidiaries[].employees) as avg_employees, sum(company.subsidiaries[].financials.revenue) as total_revenue group by company.subsidiaries[].headquarters.country\""
  "jonq $JSON_PATH/complex.json \"select company.subsidiaries[].headquarters.country, count(*) as count, avg(company.subsidiaries[].financials.profit) as avg_profit group by company.subsidiaries[].headquarters.country having avg_profit > 10000000\""
  "jonq $JSON_PATH/complex.json \"select type, count(*) as count, min(versions[].pricing.monthly) as min_price, max(versions[].pricing.monthly) as max_price, avg(versions[].pricing.monthly) as avg_price group by type from products[]\""
  "jonq $JSON_PATH/complex.json \"select type, avg(versions[].pricing.yearly) as avg_yearly, avg(versions[].pricing.monthly) as avg_monthly group by type from products[] having avg_yearly > 2000\""
  "jonq $JSON_PATH/complex.json \"select products[].customers[].industry, count(*) as count group by products[].customers[].industry\""
  "jonq $JSON_PATH/complex.json \"select products[].customers[].industry, count(*) as count group by products[].customers[].industry having count > 1\""
  "jonq $JSON_PATH/complex.json \"select sum(products[].versions[].pricing.monthly) as total_monthly, avg(products[].versions[].pricing.monthly) as avg_monthly, count(products[].versions[]) as version_count\""
  "jonq $JSON_PATH/complex.json \"select avg(products[].versions[].pricing.yearly / 12) as yearly_monthly_ratio\""
  "jonq $JSON_PATH/complex.json \"select type, avg(versions[].pricing.yearly / 12) as yearly_monthly_ratio group by type from products[] having yearly_monthly_ratio > 200\""
  "jonq $JSON_PATH/complex.json \"select products[].name, count(products[].versions[]) as version_count, count(products[].customers[]) as customer_count\""
  "jonq $JSON_PATH/complex.json \"select type, avg(versions[].pricing.monthly) as avg_price group by type sort avg_price desc from products[]\""
  "jonq $JSON_PATH/complex.json \"select launched, avg(versions[].pricing.monthly) as avg_monthly_price group by launched from products[] having avg_monthly_price > 200\""
  "jonq $JSON_PATH/complex.json \"select max(products[].versions[].pricing.monthly) - min(products[].versions[].pricing.monthly) as price_range\""
  "jonq $JSON_PATH/complex.json \"select name from products[] if versions[].pricing.monthly > 200 and customers[].industry == 'Manufacturing'\""
  "jonq $JSON_PATH/complex.json \"select id, name from products[] if versions[].pricing.monthly > 200 and versions[].pricing.yearly < 3000\""
  "jonq $JSON_PATH/complex.json \"select type, avg(versions[].pricing.monthly) as avg_monthly, count(*) as count group by type having avg_monthly > 200 and count > 0 from products[]\""
)

echo -e "\n====================================================="
echo "SIMPLE JSON EDGE CASES"
echo "====================================================="

for cmd in "${simple_json_edge_cases[@]}"; do
  run_command "$cmd"
done

echo -e "\n====================================================="
echo "NESTED JSON EDGE CASES"
echo "====================================================="

for cmd in "${nested_json_edge_cases[@]}"; do
  run_command "$cmd"
done

echo -e "\n====================================================="
echo "COMPLEX JSON EDGE CASES"
echo "====================================================="

for cmd in "${complex_json_edge_cases[@]}"; do
  run_command "$cmd"
done

# Print final test summary
print_summary

echo "-----------------------------------------"
echo "Test script completed"
echo "-----------------------------------------"