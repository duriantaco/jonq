import csv
import io
from jonq.csv_utils import flatten_json, json_to_csv

class TestFlattenJson:
    def test_flat_object(self):
        """Test flattening a simple flat object."""
        data = {"name": "Alice", "age": 30}
        flattened = flatten_json(data)
        assert flattened == {"name": "Alice", "age": 30}
    
    def test_nested_object(self):
        """Test flattening a nested object."""
        data = {
            "name": "Alice",
            "address": {
                "city": "New York",
                "zip": "10001"
            }
        }
        flattened = flatten_json(data)
        assert flattened == {
            "name": "Alice",
            "address.city": "New York",
            "address.zip": "10001"
        }
    
    def test_deeply_nested_object(self):
        """Test flattening a deeply nested object."""
        data = {
            "user": {
                "profile": {
                    "address": {
                        "city": "New York",
                        "zip": "10001"
                    }
                }
            }
        }
        flattened = flatten_json(data)
        assert flattened == {
            "user.profile.address.city": "New York",
            "user.profile.address.zip": "10001"
        }
    
    def test_array(self):
        """Test flattening an array."""
        data = [1, 2, 3]
        flattened = flatten_json(data)
        assert flattened == {"0": 1, "1": 2, "2": 3}
    
    def test_object_with_array(self):
        """Test flattening an object containing an array."""
        data = {
            "name": "Alice",
            "scores": [85, 90, 95]
        }
        flattened = flatten_json(data)
        assert flattened == {
            "name": "Alice",
            "scores.0": 85,
            "scores.1": 90,
            "scores.2": 95
        }
    
    def test_array_of_objects(self):
        """Test flattening an array of objects."""
        data = [
            {"name": "Alice", "age": 30},
            {"name": "Bob", "age": 25}
        ]
        flattened = flatten_json(data)
        assert flattened == {
            "0.name": "Alice",
            "0.age": 30,
            "1.name": "Bob",
            "1.age": 25
        }
    
    def test_mixed_nested_structure(self):
        """Test flattening a complex mixed structure."""
        data = {
            "name": "Alice",
            "orders": [
                {
                    "id": 1,
                    "items": [
                        {"product": "Book", "price": 10},
                        {"product": "Pen", "price": 5}
                    ]
                },
                {
                    "id": 2,
                    "items": [
                        {"product": "Notebook", "price": 15}
                    ]
                }
            ]
        }
        flattened = flatten_json(data)
        assert flattened == {
            "name": "Alice",
            "orders.0.id": 1,
            "orders.0.items.0.product": "Book",
            "orders.0.items.0.price": 10,
            "orders.0.items.1.product": "Pen",
            "orders.0.items.1.price": 5,
            "orders.1.id": 2,
            "orders.1.items.0.product": "Notebook",
            "orders.1.items.0.price": 15
        }
    
    def test_empty_object(self):
        """Test flattening an empty object."""
        data = {}
        flattened = flatten_json(data)
        assert flattened == {}
    
    def test_empty_array(self):
        """Test flattening an empty array."""
        data = []
        flattened = flatten_json(data)
        assert flattened == {}
    
    def test_null_values(self):
        """Test flattening object with null values."""
        data = {"name": "Alice", "age": None}
        flattened = flatten_json(data)
        assert flattened == {"name": "Alice", "age": None}
    
    def test_special_characters_in_keys(self):
        """Test flattening object with special characters in keys."""
        data = {"user.name": "Alice", "user-id": 123}
        flattened = flatten_json(data)
        assert flattened == {"user.name": "Alice", "user-id": 123}
    
    def test_custom_separator(self):
        """Test flattening with custom separator."""
        data = {
            "user": {
                "name": "Alice",
                "address": {"city": "New York"}
            }
        }
        flattened = flatten_json(data, sep='_')
        assert flattened == {
            "user_name": "Alice",
            "user_address_city": "New York"
        }


class TestJsonToCsv:
    def test_simple_json_to_csv(self):
        """Test converting simple JSON to CSV."""
        data = [
            {"name": "Alice", "age": 30},
            {"name": "Bob", "age": 25}
        ]
        csv_str = json_to_csv(data)
        
        reader = csv.DictReader(io.StringIO(csv_str))
        rows = list(reader)
        
        assert len(rows) == 2
        assert rows[0]["name"] == "Alice"
        assert rows[0]["age"] == "30"
        assert rows[1]["name"] == "Bob"
        assert rows[1]["age"] == "25"
    
    def test_nested_json_to_csv(self):
        """Test converting nested JSON to CSV."""
        data = [
            {
                "name": "Alice",
                "address": {"city": "New York", "zip": "10001"}
            },
            {
                "name": "Bob",
                "address": {"city": "Chicago", "zip": "60601"}
            }
        ]
        csv_str = json_to_csv(data)
        
        reader = csv.DictReader(io.StringIO(csv_str))
        rows = list(reader)
        
        assert len(rows) == 2
        assert rows[0]["name"] == "Alice"
        assert rows[0]["address.city"] == "New York"
        assert rows[0]["address.zip"] == "10001"
        assert rows[1]["name"] == "Bob"
        assert rows[1]["address.city"] == "Chicago"
        assert rows[1]["address.zip"] == "60601"
    
    def test_json_with_arrays_to_csv(self):
        """Test converting JSON with arrays to CSV."""
        data = [
            {"name": "Alice", "scores": [90, 85, 95]},
            {"name": "Bob", "scores": [80, 75, 85]}
        ]
        csv_str = json_to_csv(data)
        
        reader = csv.DictReader(io.StringIO(csv_str))
        rows = list(reader)
        
        assert len(rows) == 2
        assert rows[0]["name"] == "Alice"
        assert rows[0]["scores.0"] == "90"
        assert rows[0]["scores.1"] == "85"
        assert rows[0]["scores.2"] == "95"
        assert rows[1]["name"] == "Bob"
        assert rows[1]["scores.0"] == "80"
        assert rows[1]["scores.1"] == "75"
        assert rows[1]["scores.2"] == "85"
    
    def test_json_string_to_csv(self):
        """Test converting JSON string to CSV."""
        json_str = '[{"name":"Alice","age":30},{"name":"Bob","age":25}]'
        csv_str = json_to_csv(json_str)
        
        reader = csv.DictReader(io.StringIO(csv_str))
        rows = list(reader)
        
        assert len(rows) == 2
        assert rows[0]["name"] == "Alice"
        assert rows[0]["age"] == "30"
        assert rows[1]["name"] == "Bob"
        assert rows[1]["age"] == "25"
    
    def test_single_object_to_csv(self):
        """Test converting a single object to CSV."""
        data = {"name": "Alice", "age": 30}
        csv_str = json_to_csv(data)
        
        reader = csv.DictReader(io.StringIO(csv_str))
        rows = list(reader)
        
        assert len(rows) == 1
        assert rows[0]["name"] == "Alice"
        assert rows[0]["age"] == "30"
    
    def test_empty_array_to_csv(self):
        """Test converting an empty array to CSV."""
        data = []
        csv_str = json_to_csv(data)
        assert csv_str == ""
    
    def test_empty_object_to_csv(self):
        """Test converting an empty object to CSV."""
        data = {}
        csv_str = json_to_csv(data)
        
        reader = csv.DictReader(io.StringIO(csv_str))
        rows = list(reader)
        
        assert len(rows) == 1
        assert "_empty" in rows[0]
        assert rows[0]["_empty"] == ""
    
    def test_array_of_simple_values_to_csv(self):
        """Test converting an array of simple values to CSV."""
        data = [1, 2, 3, 4, 5]
        csv_str = json_to_csv(data)
        
        reader = csv.DictReader(io.StringIO(csv_str))
        rows = list(reader)
        
        assert len(rows) == 5
        assert all("value" in row for row in rows)
        assert [row["value"] for row in rows] == ["1", "2", "3", "4", "5"]
    
    def test_mixed_objects_to_csv(self):
        """Test converting objects with different fields to CSV."""
        data = [
            {"name": "Alice", "age": 30},
            {"name": "Bob", "city": "Chicago"},
            {"age": 25, "city": "New York"}
        ]
        csv_str = json_to_csv(data)
        
        reader = csv.DictReader(io.StringIO(csv_str))
        rows = list(reader)
        
        assert len(rows) == 3
        assert rows[0]["name"] == "Alice"
        assert rows[0]["age"] == "30"
        assert rows[0]["city"] == ""
        assert rows[1]["name"] == "Bob"
        assert rows[1]["city"] == "Chicago"
        assert rows[1]["age"] == ""
        assert rows[2]["age"] == "25"
        assert rows[2]["city"] == "New York"
        assert rows[2]["name"] == ""
    
    def test_complex_nested_to_csv(self):
        """Test converting complex nested structure to CSV."""
        data = {
            "user": {
                "name": "Alice",
                "orders": [
                    {"id": 1, "items": [{"name": "Book", "price": 10}]},
                    {"id": 2, "items": [{"name": "Pen", "price": 5}]}
                ]
            }
        }
        csv_str = json_to_csv(data)
        
        reader = csv.DictReader(io.StringIO(csv_str))
        rows = list(reader)
        
        assert len(rows) == 1
        assert rows[0]["user.name"] == "Alice"
        assert rows[0]["user.orders.0.id"] == "1"
        assert rows[0]["user.orders.0.items.0.name"] == "Book"
        assert rows[0]["user.orders.0.items.0.price"] == "10"
        assert rows[0]["user.orders.1.id"] == "2"
        assert rows[0]["user.orders.1.items.0.name"] == "Pen"
        assert rows[0]["user.orders.1.items.0.price"] == "5"
    
    def test_non_ascii_characters(self):
        """Test handling non-ASCII characters."""
        data = [
            {"name": "José", "city": "São Paulo"},
            {"name": "François", "city": "Münich"}
        ]
        csv_str = json_to_csv(data)
        
        reader = csv.DictReader(io.StringIO(csv_str))
        rows = list(reader)
        
        assert len(rows) == 2
        assert rows[0]["name"] == "José"
        assert rows[0]["city"] == "São Paulo"
        assert rows[1]["name"] == "François"
        assert rows[1]["city"] == "Münich"