#!/bin/bash

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

JSON_PATH="/Users/oha/jonq/tests/json_test_files"

run_command() {
  echo -e "\n-----------------------------------------"
  echo -e "${YELLOW}RUNNING:${NC} $1"
  echo "-----------------------------------------"
  
  output=$(eval $1 2>&1)
  exit_status=$?
  
  if [ $exit_status -ne 0 ] || [[ "$output" == *"Error"* ]]; then
    echo -e "${RED}ERROR:${NC}"
    echo -e "${RED}$output${NC}"
  else
    echo -e "${GREEN}SUCCESS${NC}"
    echo "$output" | head -n 10
    if [ $(echo "$output" | wc -l) -gt 10 ]; then
      echo "..."
    fi
  fi
  echo
}

commands=(
  # simpl JSON tests
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
  
  # nested JSON tests
  "jonq $JSON_PATH/nested.json \"select name, profile.age\""
  "jonq $JSON_PATH/nested.json \"select name, profile.address.city\""
  "jonq $JSON_PATH/nested.json \"select name, count(orders) as order_count\""
  "jonq $JSON_PATH/nested.json \"select name, orders[0].item as first_item\""
  "jonq $JSON_PATH/nested.json \"select name if orders[0].price > 1000\""
  "jonq $JSON_PATH/nested.json \"select profile.address.city, avg(profile.age) as avg_age group by profile.address.city\""
  "jonq $JSON_PATH/nested.json \"select profile.address.city, avg(profile.age) as avg_age group by profile.address.city having avg_age > 25\""
  "jonq $JSON_PATH/nested.json \"select order_id, item, price from [].orders\""
  "jonq $JSON_PATH/nested.json \"select order_id, item, price from [].orders if price > 800\""
  
  # complex JSON tests
  "jonq $JSON_PATH/complex.json \"select company.name, company.headquarters.city\""
  "jonq $JSON_PATH/complex.json \"select name, founded from company.subsidiaries[] if founded > 2008\""
  "jonq $JSON_PATH/complex.json \"select avg(products[].versions[].pricing.monthly) as avg_price\""
  "jonq $JSON_PATH/complex.json \"select sum(company.subsidiaries[].financials.profit) as total_profit\""
  "jonq $JSON_PATH/complex.json \"select name, avg(versions[].pricing.monthly) as avg_monthly_price from products[]\""
)

echo "Running all jonq test queries..."
echo "Any errors will be highlighted in red."
echo

for cmd in "${commands[@]}"; do
  run_command "$cmd"
done

echo "-----------------------------------------"
echo "Test script completed"
echo "-----------------------------------------"