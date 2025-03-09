#!/bin/bash

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' 

# Simple.json tests
echo -e "${BLUE}Running tests for simple.json${NC}"

echo -e "${GREEN}Test 1: select *${NC}"
jonq simple.json "select *"
echo ""

echo -e "${GREEN}Test 2: select name, age${NC}"
jonq simple.json "select name, age"
echo ""

echo -e "${GREEN}Test 3: select name, age if age > 30${NC}"
jonq simple.json "select name, age if age > 30"
echo ""

echo -e "${GREEN}Test 4: select name, age sort age desc 2${NC}"
jonq simple.json "select name, age sort age desc 2"
echo ""

echo -e "${GREEN}Test 5: select sum(age) as total_age${NC}"
jonq simple.json "select sum(age) as total_age"
echo ""

echo -e "${GREEN}Test 6: select avg(age) as total_age${NC}"
jonq simple.json "select avg(age) as total_age"
echo ""

echo -e "${GREEN}Test 7: select count(age) as total_age${NC}"
jonq simple.json "select count(age) as total_age"
echo ""

echo -e "${GREEN}Test 8: select name, age if age > 30 or city = 'New York'${NC}"
jonq simple.json "select name, age if age > 30 or city = 'New York'"
echo ""

echo -e "${GREEN}Test 9: select name, age if age < 30 and city = 'Los Angeles'${NC}"
jonq simple.json "select name, age if age < 30 and city = 'Los Angeles'"
echo ""

echo -e "${GREEN}Test 10: select name, age if (age > 30 and city = 'Chicago') or (age < 30 and city = 'Los Angeles')${NC}"
jonq simple.json "select name, age if (age > 30 and city = 'Chicago') or (age < 30 and city = 'Los Angeles')"
echo ""

echo -e "${GREEN}Test 11: select city, count(*) as count group by city${NC}"
jonq simple.json "select city, count(*) as count group by city"
echo ""

echo -e "${GREEN}Test 12: select city, avg(age) as avg_age group by city${NC}"
jonq simple.json "select city, avg(age) as avg_age group by city"
echo ""