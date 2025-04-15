from jonq.tokenizer import tokenize
from jonq.query_parser import parse_query, tokenize_query

def print_parsed_query(query):
    """Parse a query and print its components for inspection"""
    print(f"\nQuery: {query}")
    print("-" * 50)
    
    try:
        tokens = tokenize_query(query)
        print(f"Tokens: {tokens}")
        
        fields, condition, group_by, having, order_by, sort_direction, limit = parse_query(tokens)
        
        print("\nParsed Components:")
        print(f"  Fields: {fields}")
        print(f"  Condition: {condition}")
        print(f"  Group By: {group_by}")
        print(f"  Having: {having}")
        print(f"  Order By: {order_by}")
        print(f"  Sort Direction: {sort_direction}")
        print(f"  Limit: {limit}")
        
        print("\n✅ Parsing Successful")
        return True
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        return False

def run_having_tests():
    """Test various HAVING clause scenarios"""
    print("\n=== TESTING HAVING CLAUSE ===\n")
    
    query1 = "select city, count(*) as count group by city having count > 1"
    success1 = print_parsed_query(query1)
    
    query2 = "select department, avg(salary) as avg_salary group by department having avg_salary > 50000"
    success2 = print_parsed_query(query2)
    
    query3 = "select city, count(*) as count, avg(age) as avg_age group by city having count > 2 and avg_age > 30"
    success3 = print_parsed_query(query3)
    
    query4 = "select department, count(*) as count group by department having (count > 5 or count < 2)"
    success4 = print_parsed_query(query4)
    
    query5 = "select name, age having age > 30"
    success5 = not print_parsed_query(query5)
    
    print("\n=== HAVING CLAUSE TEST RESULTS ===")
    print(f"Test 1 (Basic HAVING): {'PASSED' if success1 else 'FAILED'}")
    print(f"Test 2 (HAVING with aggregate): {'PASSED' if success2 else 'FAILED'}")
    print(f"Test 3 (HAVING with complex condition): {'PASSED' if success3 else 'FAILED'}")
    print(f"Test 4 (HAVING with parentheses): {'PASSED' if success4 else 'FAILED'}")
    print(f"Test 5 (HAVING without GROUP BY): {'PASSED' if success5 else 'FAILED'}")
    
    all_passed = success1 and success2 and success3 and success4 and success5
    print(f"\nOverall Result: {'PASSED' if all_passed else 'FAILED'}")

if __name__ == "__main__":
    run_having_tests()