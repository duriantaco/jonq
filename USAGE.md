# USAGE GUIDE

## simple.json

```json
[
  {"id": 1, "name": "Alice", "age": 30, "city": "New York"},
  {"id": 2, "name": "Bob", "age": 25, "city": "Los Angeles"},
  {"id": 3, "name": "Charlie", "age": 35, "city": "Chicago"}
]
```
1. Basic Selection

### Select all fields:

Input: `jonq json_test_files/simple.json "select *"`

```json
[
  {
    "id": 1,
    "name": "Alice",
    "age": 30,
    "city": "New York"
  },
  {
    "id": 2,
    "name": "Bob",
    "age": 25,
    "city": "Los Angeles"
  },
  {
    "id": 3,
    "name": "Charlie",
    "age": 35,
    "city": "Chicago"
  }
]
```

### Select specific fields:

Input: `jonq json_test_files/simple.json "select name, age"`

```json
[
    {
    "name": "Alice",
    "age": 30
  },
  {
    "name": "Bob",
    "age": 25
  },
  {
    "name": "Charlie",
    "age": 35
  }
]
```
2. Filtering with Conditions

### Basic filtering:

Input: `jonq json_test_files/simple.json "select name, age if age > 30"`

```json
[{
    "name": "Charlie",
    "age": 35
  }
]
```

3. Sorting and Limiting

### Sort descending with limit:

Input: `jonq json_test_files/simple.json "select name, age sort age desc 2"`

```json
[
{
    "name": "Charlie",
    "age": 35
  },
  {
    "name": "Alice",
    "age": 30
  }
]
```

4. Aggregation Functions

### Sum: 

Input: `jonq json_test_files/simple.json "select sum(age) as total_age"`

```json
{
  "total_age": 90
}
```

### Average:

Input: `jonq json_test_files/simple.json "select avg(age) as total_age"`

```json
{
  "total_age": 30
}
```

### Count:

Input: `jonq json_test_files/simple.json "select count(age) as total_age"`

```json
{
  "total_age": 3
}
```

### Min/Max:

Input: `jonq simple.json "select min(age) as youngest, max(age) as oldest"`

```json
{
  "youngest": 25,
  "oldest": 35
}
```

5. Grouping and Having

### Group by single field:

Input: `jonq simple.json "select city, count(*) as count group by city"`

```json
[
  {
    "city": "Chicago",
    "count": 1
  },
  {
    "city": "Los Angeles",
    "count": 1
  },
  {
    "city": "New York",
    "count": 1
  }
]
```

### Group by with aggregation:

Input: `jonq simple.json "select city, avg(age) as avg_age group by city"`

```json
[
  {
    "city": "Chicago",
    "avg_age": 35
  },
  {
    "city": "Los Angeles",
    "avg_age": 25
  },
  {
    "city": "New York",
    "avg_age": 30
  }
]
```

### Group by with HAVING clause:

Input: `jonq simple.json "select city, count(*) as count group by city having count >= 1"`

```json
[
  {
    "city": "Chicago",
    "count": 1
  },
  {
    "city": "Los Angeles",
    "count": 1
  },
  {
    "city": "New York",
    "count": 1
  }
]
```

=====================================================

## nested.json

```json
[
  {
    "id": 1, "name": "Alice",
    "profile": {
      "age": 30,
      "address": {"city": "New York", "zip": "10001"}
    },
    "orders": [
      {"order_id": 101, "item": "Laptop", "price": 1200},
      {"order_id": 102, "item": "Phone", "price": 800}
    ]
  },
  {
    "id": 2, "name": "Bob",
    "profile": {
      "age": 25,
      "address": {"city": "Los Angeles", "zip": "90001"}
    },
    "orders": [
      {"order_id": 103, "item": "Tablet", "price": 500}
    ]
  }
]
```

1. Basic Selection

### Access nested fields:

Input: `jonq json_test_files/nested.json "select name, profile.age"` 

```json
[
    {
    "name": "Alice",
    "age": 30
  },
  {
    "name": "Bob",
    "age": 25
  }
]
```

### Access deeply nested fields:

Input: `jonq json_test_files/nested.json "select name, profile.address.city"` 

```json
[
{
    "name": "Alice",
    "city": "New York"
  },
  {
    "name": "Bob",
    "city": "Los Angeles"
  }
]
```

2. Array Operations

### Count array items:

Input: `jonq json_test_files/nested.json "select name, count(orders) as order_count"`

```json
[
  {
    "name": "Alice",
    "order_count": 2
  },
  {
    "name": "Bob",
    "order_count": 1
  }
]
```

### Access array elements:

Input: `jonq nested.json "select name, orders[0].item as first_item"`

```json
[
  {
    "name": "Alice",
    "first_item": "Laptop"
  },
  {
    "name": "Bob",
    "first_item": "Tablet"
  }
]
```

### Filter by array properties:

Input: `jonq nested.json "select name if orders[0].price > 1000"`

```json
[
  {
    "name": "Alice"
  }
]
```

3. Grouping and Having

### Group by with nested fields:

Input: `jonq nested.json "select profile.address.city, avg(profile.age) as avg_age group by profile.address.city"`

```json
[
  {
    "city": "Los Angeles",
    "avg_age": 25
  },
  {
    "city": "New York",
    "avg_age": 30
  }
]
```

### Group by with HAVING on aggregated value:

Input: `jonq nested.json "select profile.address.city, avg(profile.age) as avg_age group by profile.address.city having avg_age > 25"`

```json
[
  {
    "city": "New York",
    "avg_age": 30
  }
]
```

=====================================================

## complex.json

```json
{
    "company": {
      "name": "TechCorp Global",
      "founded": 2005,
      "headquarters": {
        "address": "123 Innovation Way",
        "city": "San Francisco",
        "country": "USA",
        "coordinates": {
          "latitude": 37.7749,
          "longitude": -122.4194
        }
      },
      "subsidiaries": [
        {
          "name": "TechCorp Asia",
          "founded": 2010,
          "headquarters": {
            "city": "Singapore",
            "country": "Singapore"
          },
          "employees": 250,
          "financials": {
            "revenue": 42000000,
            "profit": 8500000
          }
        },
        {
          "name": "TechCorp Europe",
          "founded": 2008,
          "headquarters": {
            "city": "Berlin",
            "country": "Germany"
          },
          "employees": 300,
          "financials": {
            "revenue": 58000000,
            "profit": 12000000
          }
        }
      ]
    },
    "products": [
      {
        "id": "P001",
        "name": "Enterprise Suite",
        "type": "Software",
        "launched": 2012,
        "versions": [
          {
            "version": "1.0",
            "released": "2012-05-15",
            "pricing": {
              "monthly": 199.99,
              "yearly": 1999.99
            }
          },
          {
            "version": "2.0",
            "released": "2015-06-30",
            "pricing": {
              "monthly": 299.99,
              "yearly": 2999.99
            }
          }
        ],
        "customers": [
          {"id": "C001", "name": "Acme Corp", "industry": "Manufacturing"},
          {"id": "C002", "name": "Globex", "industry": "Finance"}
        ]
      },
      {
        "id": "P002",
        "name": "Security Shield",
        "type": "Software",
        "launched": 2015,
        "versions": [
          {
            "version": "1.0",
            "pricing": {
              "monthly": 149.99,
              "yearly": 1499.99
            }
          }
        ],
        "customers": [
          {"id": "C001", "name": "Acme Corp", "industry": "Manufacturing"},
          {"id": "C003", "name": "Initech", "industry": "Technology"}
        ]
      }
    ]
  }
```

1. Selection

### Access multiple levels of nesting:

Input: `jonq complex.json "select company.name, company.headquarters.city"`

```json
[
  {
    "name": "TechCorp Global",
    "city": "San Francisco"
  }
]
```

### Combine aggregation of nested arrays:

Input: `jonq complex.json "select avg(products[].versions[].pricing.monthly) as avg_price"`

```json
{
  "avg_price": 216.65666666666667
}
```