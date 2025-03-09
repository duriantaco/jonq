# hello_world.json tests

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' 

echo -e "${BLUE}Running tests for hello_world.json${NC}"

echo -e "${GREEN}Test 1: select *${NC}"
jonq hello_world.json "select *"
echo ""

echo -e "${GREEN}Test 2: select name, age${NC}"
jonq hello_world.json "select name, age"
echo ""

echo -e "${GREEN}Test 3: select name, age if age > 30${NC}"
jonq hello_world.json "select name, age if age > 30"
echo ""

## simple_number.json

echo -e "${BLUE}Running tests for simple_number.json${NC}"

echo -e "${GREEN}Test 4: select *${NC}"
jonq simple_number.json "select *"
echo ""

echo -e "${GREEN}Test 5: select number${NC}"
jonq simple_number.json "select number"
echo ""

echo -e "${GREEN}Test 6: select number if number > 5${NC}"
jonq simple_number.json "select number if number > 5"
echo ""

## special_characters_keys.json

echo -e "${BLUE}Running tests for special_characters_keys.json${NC}"

echo -e "${GREEN}Test 7: select *${NC}"
jonq special_characters_keys.json "select *"
echo ""

echo -e "${GREEN}Test 8: select 'special key'${NC}"
jonq special_characters_keys.json "select 'special key'"
echo ""

echo -e "${GREEN}Test 9: select 'special key' if 'special key' > 5${NC}"
jonq special_characters_keys.json "select 'special key' if 'special key' > 5"
echo ""


## special_value.json

echo -e "${BLUE}Running tests for special_value.json${NC}"

echo -e "${GREEN}Test 10: select *${NC}"
jonq special_value.json "select *"
echo ""

echo -e "${GREEN}Test 11: select 'special value'${NC}"
jonq special_value.json "select 'special value'"
echo ""

echo -e "${GREEN}Test 12: select 'special value' if 'special value' > 5${NC}"
jonq special_value.json "select 'special value' if 'special value' > 5"
echo ""

## nested_array.json

echo -e "${BLUE}Running tests for nested_array.json${NC}"

echo -e "${GREEN}Test 13: select *${NC}"
jonq nested_array.json "select *"
echo ""

echo -e "${GREEN}Test 14: select name, age${NC}"
jonq nested_array.json "select name, age"
echo ""

echo -e "${GREEN}Test 15: select name, age if age > 30${NC}"
jonq nested_array.json "select name, age if age > 30"
echo ""

## mixed_arrays.json

echo -e "${BLUE}Running tests for mixed_arrays.json${NC}"

echo -e "${GREEN}Test 16: select *${NC}"
jonq mixed_arrays.json "select *"
echo ""

echo -e "${GREEN}Test 17: select name, age${NC}"
jonq mixed_arrays.json "select name, age"
echo ""

echo -e "${GREEN}Test 18: select name, age if age > 30${NC}"
jonq mixed_arrays.json "select name, age if age > 30"
echo ""

## deeply_nested.json

echo -e "${BLUE}Running tests for deeply_nested.json${NC}"

echo -e "${GREEN}Test 19: select *${NC}"
jonq deeply_nested.json "select *"
echo ""

echo -e "${GREEN}Test 20: select name, age${NC}"
jonq deeply_nested.json "select name, age"
echo ""

echo -e "${GREEN}Test 21: select name, age if age > 30${NC}"
jonq deeply_nested.json "select name, age if age > 30"
echo ""

## empty_object_array.json

echo -e "${BLUE}Running tests for empty_object_array.json${NC}"

echo -e "${GREEN}Test 22: select *${NC}"
jonq empty_object_array.json "select *"
echo ""

echo -e "${GREEN}Test 23: select name, age${NC}"
jonq empty_object_array.json "select name, age"
echo ""

echo -e "${GREEN}Test 24: select name, age if age > 30${NC}"
jonq empty_object_array.json "select name, age if age > 30"
echo ""

