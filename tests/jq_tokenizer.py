import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jonq.tokenizer import tokenize

def run_test(query, expected_tokens, test_name):
    try:
        tokens = tokenize(query)
        if tokens == expected_tokens:
            print(f"✅ {test_name}: PASSED")
            return True
        else:
            print(f"❌ {test_name}: FAILED")
            print(f"  Expected: {expected_tokens}")
            print(f"  Got:      {tokens}")
            return False
    except Exception as e:
        print(f"❌ {test_name}: EXCEPTION - {str(e)}")
        return False

def test_basic_queries():
    query = "select *"
    expected = ["select", "*"]
    run_test(query, expected, "Simple SELECT *")
    
    query = "select name, age"
    expected = ["select", "name", ",", "age"]
    run_test(query, expected, "SELECT with fields")
    
    query = "select name, age if age > 30"
    expected = ["select", "name", ",", "age", "if", "age", ">", "30"]
    run_test(query, expected, "SELECT with condition")

def test_function_calls():
    query = "select count(*) as total"
    expected = ["select", "count", "(", "*", ")", "as", "total"]
    run_test(query, expected, "SELECT with count(*)")
    
    query = "select sum(age) as total_age"
    expected = ["select", "sum", "(", "age", ")", "as", "total_age"]
    run_test(query, expected, "SELECT with function parameter")
    
    query = "select avg(age) as avg_age, max(salary) as max_salary"
    expected = ["select", "avg", "(", "age", ")", "as", "avg_age", ",", "max", "(", "salary", ")", "as", "max_salary"]
    run_test(query, expected, "Multiple functions")
    
    query = "select sum(age) * 2 as double_age"
    expected = ["select", "sum", "(", "age", ")", "*", "2", "as", "double_age"]
    run_test(query, expected, "Arithmetic with functions")

def test_complex_queries():
    query = "select city, count(*) as count group by city"
    expected = ["select", "city", ",", "count", "(", "*", ")", "as", "count", "group", "by", "city"]
    run_test(query, expected, "GROUP BY")
    
    query = "select city, count(*) as count group by city having count > 1"
    expected = ["select", "city", ",", "count", "(", "*", ")", "as", "count", "group", "by", "city", "having", "count", ">", "1"]
    run_test(query, expected, "HAVING clause")
    
    query = "select name if (age > 30 and city = 'New York') or (age < 20 and city = 'Los Angeles')"
    expected = [
        "select", "name", "if", "(", "age", ">", "30", "and", "city", "=", "'New York'", ")", 
        "or", "(", "age", "<", "20", "and", "city", "=", "'Los Angeles'", ")"
    ]
    run_test(query, expected, "Complex condition")
    
    query = "select name, age sort age desc 5"
    expected = ["select", "name", ",", "age", "sort", "age", "desc", "5"]
    run_test(query, expected, "Sorting and limit")

def test_special_cases():
    query = "select 'first name', \"last name\""
    expected = ["select", "'first name'", ",", "\"last name\""]
    run_test(query, expected, "Quoted field names")
    
    query = "select name if name = 'John\\'s'"
    expected = ["select", "name", "if", "name", "=", "'John\\'s'"]
    run_test(query, expected, "Escaped quotes in strings")
    
    query = "select person.name, person.address.city"
    expected = ["select", "person.name", ",", "person.address.city"]
    run_test(query, expected, "Nested fields")
    
    query = "select orders[0].item, orders[1].price"
    expected = ["select", "orders[0].item", ",", "orders[1].price"]
    run_test(query, expected, "Array indexing")

def test_error_cases():
    query = "select name if name = 'John"
    try:
        tokens = tokenize(query)
        print("❌ Unbalanced quotes: FAILED - Should have raised an exception")
    except Exception as e:
        print(f"✅ Unbalanced quotes: PASSED - Got expected exception: {str(e)}")
    
    query = "select name; drop table users;"
    try:
        tokens = tokenize(query)
        print("❌ Invalid character: FAILED - Should have raised an exception")
    except Exception as e:
        print(f"✅ Invalid character: PASSED - Got expected exception: {str(e)}")

if __name__ == "__main__":
    print("RUNNING TOKENIZER TESTS")
    print("=======================")
    test_basic_queries()
    test_function_calls()
    test_complex_queries()
    test_special_cases()
    test_error_cases()
    print("=======================")
    print("TOKENIZER TESTS COMPLETED")