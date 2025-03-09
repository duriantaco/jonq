# USAGE GUIDE

## simple.json

1. Input: `jonq json_test_files/simple.json "select *"`

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

2. Input: `jonq json_test_files/simple.json "select name, age"`

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

3. Input: `jonq json_test_files/simple.json "select name, age if age > 30"`

```json
[{
    "name": "Charlie",
    "age": 35
  }
]
```

4. Input: `jonq json_test_files/simple.json "select name, age sort age desc 2"`

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

5. Input: `jonq json_test_files/simple.json "select sum(age) as total_age"`

```json
{
  "total_age": 90
}
```

6. Input: `jonq json_test_files/simple.json "select avg(age) as total_age"`

```json
{
  "total_age": 30
}
```

7. Input: `jonq json_test_files/simple.json "select count(age) as total_age"`

```json
{
  "total_age": 3
}
```

## nested.json

1. Input: `jonq json_test_files/nested.json "select name, profile.age"` 

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

2. Input: `jonq json_test_files/nested.json "select name, profile.address.city"` 

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

3. Input: `jonq json_test_files/nested.json "select name, count(orders) as order_count"`

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