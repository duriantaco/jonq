#!/bin/bash

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' 

echo -e "${BLUE}Running tests for nested.json${NC}"

echo -e "${GREEN}Test 1: select name, profile.age${NC}"
jonq nested.json "select name, profile.age"
echo ""

echo -e "${GREEN}Test 2: select name, profile.address.city${NC}"
jonq nested.json "select name, profile.address.city"
echo ""

echo -e "${GREEN}Test 3: select name, count(orders) as order_count${NC}"
jonq nested.json "select name, count(orders) as order_count"
echo ""

echo -e "${GREEN}Test 4: select name, max(orders.price) - min(orders.price)${NC}"
jonq nested.json "select name, max(orders.price) - min(orders.price)"
echo ""

echo -e "${GREEN}Test 5: select name, profile.age if profile.address.city = 'New York' or orders[0].price > 1000${NC}"
jonq nested.json "select name, profile.age if profile.address.city = 'New York' or orders[0].price > 1000"
echo ""

echo -e "${GREEN}Test 6: select name, profile.age if profile.age < 30 and profile.address.city = 'Los Angeles'${NC}"
jonq nested.json "select name, profile.age if profile.age < 30 and profile.address.city = 'Los Angeles'"
echo ""

echo -e "${GREEN}Test 7: select name, profile.age if (profile.age > 25 and profile.address.city = 'New York') or (profile.age < 26 and profile.address.city = 'Los Angeles')${NC}"
jonq nested.json "select name, profile.age if (profile.age > 25 and profile.address.city = 'New York') or (profile.age < 26 and profile.address.city = 'Los Angeles')"
echo ""

echo -e "${GREEN}Test 8: select profile.address.city, count(*) as user_count group by profile.address.city${NC}"
jonq nested.json "select profile.address.city, count(*) as user_count group by profile.address.city"
echo ""

echo -e "${GREEN}Test 9: select profile.address.city, avg(profile.age) as avg_age group by profile.address.city${NC}"
jonq nested.json "select profile.address.city, avg(profile.age) as avg_age group by profile.address.city"
echo ""

echo -e "${GREEN}Test 10: select profile.address.city, count(orders) as order_count, avg(orders.price) as avg_price group by profile.address.city${NC}"
jonq nested.json "select profile.address.city, count(orders) as order_count, avg(orders.price) as avg_price group by profile.address.city"
echo ""