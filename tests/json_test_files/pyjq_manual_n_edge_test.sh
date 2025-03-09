# simple_object.json tests

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' 

echo -e "${BLUE}Running tests for simple_object.json${NC}"

echo -e "${GREEN}Test 1: select *${NC}"
jonq single_object.json "select *"
echo ""

echo -e "${GREEN}Test 2: select name, age${NC}"
jonq single_object.json "select name, age"
echo ""

echo -e "${GREEN}Test 3: select name, age if age > 30${NC}"
jonq single_object.json "select name, age if age > 30"
echo ""

# empty_array.json
echo -e "${BLUE}Running tests for empty_array.json${NC}"

echo -e "${GREEN}Test 4: select *${NC}"
jonq empty_array.json "select *"
echo ""

echo -e "${GREEN}Test 5: select name, age${NC}"
jonq empty_array.json "select name, age"
echo ""

echo -e "${GREEN}Test 6: select avg(age) as total_age${NC}"
jonq empty_array.json "select avg(age) as total_age"
echo ""

# missing_fields.json

echo -e "${BLUE}Running tests for missing_fields.json${NC}"

echo -e "${GREEN}Test 7: select *${NC}"
jonq missing_fields.json "select *"
echo ""

echo -e "${GREEN}Test 8: select name, age${NC}"
jonq missing_fields.json "select name, age"
echo ""

echo -e "${GREEN}Test 9: select age if age > 20${NC}"
jonq missing_fields.json "select * if age > 20"
echo ""

# empty_object.json

echo -e "${BLUE}Running tests for empty_object.json${NC}"

echo -e "${GREEN}Test 10: select *${NC}"
jonq empty_object.json "select *"
echo ""

echo -e "${GREEN}Test 11: select name, age${NC}"
jonq empty_object.json "select name, age"
echo ""

echo -e "${GREEN}Test 12: select age if age > 20${NC}"
jonq empty_object.json "select * if age > 20"
echo ""

# null_values.json

echo -e "${BLUE}Running tests for null_values.json${NC}"

echo -e "${GREEN}Test 13: select *${NC}"
jonq null_values.json "select *"
echo ""

echo -e "${GREEN}Test 14: select name, age${NC}"
jonq null_values.json "select name, age"
echo ""

echo -e "${GREEN}Test 15: select age if age > 20${NC}"
jonq null_values.json "select * if age > 20"
echo ""


