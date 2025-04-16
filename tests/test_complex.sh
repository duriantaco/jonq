#!/bin/bash

echo "=== REVISED TESTING FOR COMPLEX.JSON ==="
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

echo "=== WORKING TESTS FROM PREVIOUS RUN ==="
run_test "Access multiple levels of nesting" 'jonq json_test_files/complex.json "select company.name, company.headquarters.city"'
run_test "Combine aggregation of nested arrays" 'jonq json_test_files/complex.json "select avg(products[].versions[].pricing.monthly) as avg_price"'
run_test "Access deep nested coordinates" 'jonq json_test_files/complex.json "select company.headquarters.coordinates.latitude, company.headquarters.coordinates.longitude"'
run_test "Access multiple nested fields at different levels" 'jonq json_test_files/complex.json "select company.name, company.headquarters.country, company.founded"'
run_test "Access array elements by index" 'jonq json_test_files/complex.json "select company.subsidiaries[0].name, company.subsidiaries[1].name"'
run_test "Count array elements" 'jonq json_test_files/complex.json "select count(company.subsidiaries) as subsidiary_count, count(products) as product_count"'
run_test "Calculate total employees across subsidiaries" 'jonq json_test_files/complex.json "select sum(company.subsidiaries[].employees) as total_employees"'
run_test "Calculate total revenue and profit" 'jonq json_test_files/complex.json "select sum(company.subsidiaries[].financials.revenue) as total_revenue, sum(company.subsidiaries[].financials.profit) as total_profit"'
run_test "Query subsidiary details directly" 'jonq json_test_files/complex.json "select name, employees, financials.revenue from company.subsidiaries[]"'
run_test "Query product versions" 'jonq json_test_files/complex.json "select version, pricing.monthly, pricing.yearly from products[].versions[]"'
run_test "Query customers directly" 'jonq json_test_files/complex.json "select id, name, industry from products[].customers[]"'
run_test "Filter subsidiaries by revenue" 'jonq json_test_files/complex.json "select name, financials.revenue from company.subsidiaries[] if financials.revenue > 50000000"'
run_test "Filter products by launch date" 'jonq json_test_files/complex.json "select id, name, launched from products[] if launched > 2014"'
run_test "Find subsidiaries with employees > 250 and high revenue" 'jonq json_test_files/complex.json "select name, employees, financials.revenue from company.subsidiaries[] if employees > 250 and financials.revenue > 40000000"'
run_test "Calculate min and max prices across product versions" 'jonq json_test_files/complex.json "select min(products[].versions[].pricing.monthly) as min_price, max(products[].versions[].pricing.monthly) as max_price"'
run_test "Filter, sort, and limit subsidiaries" 'jonq json_test_files/complex.json "select name, employees, financials.revenue from company.subsidiaries[] sort financials.revenue desc 1"'

echo "=== FIXED CALCULATION TESTS ==="
run_test "Simple calculation on subsidiary revenue" 'jonq json_test_files/complex.json "select name, financials.revenue, financials.profit from company.subsidiaries[]"'
run_test "Simple calculation on version pricing" 'jonq json_test_files/complex.json "select version, pricing.monthly, pricing.yearly from products[].versions[]"'

echo "=== ARRAY TESTS ==="
run_test "Get specific subsidiary details" 'jonq json_test_files/complex.json "select company.subsidiaries[0].name, company.subsidiaries[0].employees"'
run_test "Get specific product customer" 'jonq json_test_files/complex.json "select products[0].customers[0].name, products[0].customers[0].industry"'
run_test "Get specific product version" 'jonq json_test_files/complex.json "select products[0].versions[0].version, products[0].versions[0].pricing.monthly"'

echo "=== CONDITIONAL QUERIES ==="
run_test "Filter subsidiaries founded after 2008" 'jonq json_test_files/complex.json "select name, founded from company.subsidiaries[] if founded > 2008"'
run_test "Filter product by exact id" 'jonq json_test_files/complex.json "select id, name from products[] if id == \"P001\""'
run_test "Filter versions with monthly price" 'jonq json_test_files/complex.json "select version, pricing.monthly from products[].versions[] if pricing.monthly > 200"'

echo "=== SIMPLIFIED AGGREGATIONS ==="
run_test "Count subsidiaries" 'jonq json_test_files/complex.json "select count(company.subsidiaries) as count"'
run_test "Sum of all employee counts" 'jonq json_test_files/complex.json "select sum(company.subsidiaries[].employees) as total"'
run_test "Average monthly pricing" 'jonq json_test_files/complex.json "select avg(products[].versions[].pricing.monthly) as avg_price"'

echo "=== TEST COMPLETE ==="