## Basic Syntax

The general form of a jonq query is:
```bash
select [distinct] <fields> [from <path>] [if <condition>] [group by <fields> [having <condition>]] [sort <field> [asc|desc]] [limit N]
```

## SELECT Statement
Every jonq query must begin with select, followed by one or more fields to retrieve.

### Field Selection
#### Select All Fields
```bash
select *
```

#### Select Specific Fields
```bash
select name, age, city
```

#### DISTINCT
Return only unique rows:
```bash
select distinct city
select distinct name, city
```

#### Field Aliases
Use `as` to rename fields:
```bash
select name, age as years_old
```

#### Nested Fields
Use dot notation to access nested fields:
```bash
select name, profile.age, profile.address.city
```

#### Array Elements
Use square brackets to access array elements:
```bash
select name, orders[0].item, scores[1]
```

#### Fields with Special Characters
Use quotes for fields with spaces or special characters:

```bash
select 'first name', "last-name", user."login-count"
```

## Filtering with IF

Use `if` to filter results based on conditions:

### Basic Comparisons

```bash
select name, age if age > 30
select name, city if city = 'New York'
```

### Supported Operators

| Operator | Description |
|----------|-------------|
| `=`, `==` | Equal to |
| `!=` | Not equal to |
| `>` | Greater than |
| `<` | Less than |
| `>=` | Greater than or equal to |
| `<=` | Less than or equal to |
| `between` | Range check |
| `contains` | Substring check |
| `in` | Set membership |
| `like` | Pattern matching |
| `not` | Logical negation |

### Logical Operators

`and`: Logical AND
`or`: Logical OR

### Complex Conditions
```bash
select name, age if age > 25 and city = 'New York'
select name, age if age > 30 or city = 'Los Angeles'
select name, age if (age > 30 and city = 'Chicago') or (age < 25 and city = 'New York')
```

### IN Operator
Check if a field's value is in a set of values:
```bash
select * if city in ('New York', 'Chicago', 'Los Angeles')
select name if status in ('active', 'pending')
```

### NOT Operator
Negate a condition:
```bash
select * if not age > 30
select * if not city = 'New York'
```

### LIKE Operator
Pattern matching with `%` as wildcard:
```bash
select * if name like 'Al%'       # starts with "Al"
select * if name like '%ice'      # ends with "ice"
select * if name like '%li%'      # contains "li"
select * if email like '%@gmail%' # contains "@gmail"
```

### BETWEEN Operator
```bash
select name, age if age between 25 and 35
```

### CONTAINS Operator
```bash
select * if name contains 'li'
```

### Nested Field Conditions
```bash
select name if profile.age > 30
select name if orders[0].price > 100
select name if profile.address.city = 'New York'
```

## Sorting and Limiting

### Sorting
Use `sort` followed by a field name to sort results:
```bash
select name, age sort age
```

### Sort Direction
Specify `asc` (default) or `desc` for ascending or descending order:
```bash
select name, age sort age asc
select name, age sort age desc
```

### Limiting Results
Use `limit` as a standalone clause:
```bash
select name, age limit 5
select * if age > 25 limit 10
select city, count(*) as cnt group by city limit 3
```

Or add a number after the sort direction (inline limit):
```bash
select name, age sort age desc 5
```

## Aggregation Functions
jonq supports the following aggregation functions:

### count
Count the number of items:
```bash
select count(*) as user_count
select count(orders) as orders_count
```

### count(distinct)
Count unique values:
```bash
select count(distinct city) as unique_cities
select count(distinct status) as status_count
```

### sum
Calculate the sum of numeric values:
```bash
select sum(age) as total_age
select sum(orders.price) as total_sales
```

### avg
Calculate the average of numeric values:
```bash
select avg(age) as average_age
select avg(orders.price) as average_price
```

### max
Find the maximum value:
```bash
select max(age) as oldest
select max(orders.price) as highest_price
```

### min
Find the minimum value:
```bash
select min(age) as youngest
select min(orders.price) as lowest_price
```

## String Functions
jonq supports scalar string functions:

### upper
Convert to uppercase:
```bash
select upper(name) as name_upper
```

### lower
Convert to lowercase:
```bash
select lower(city) as city_lower
```

### length
Get string length:
```bash
select length(name) as name_len
```

## Math Functions
jonq supports scalar math functions:

### round
Round to nearest integer:
```bash
select round(price) as price_rounded
```

### abs
Absolute value:
```bash
select abs(balance) as abs_balance
```

### ceil
Round up:
```bash
select ceil(score) as score_ceil
```

### floor
Round down:
```bash
select floor(score) as score_floor
```

## Grouping with GROUP BY
Group data and perform aggregations per group:
```bash
select city, count(*) as user_count group by city
select city, avg(age) as avg_age group by city
select profile.address.city, count(*) as user_count group by profile.address.city
```

### HAVING
Filter groups after aggregation:
```bash
select city, count(*) as cnt group by city having cnt > 2
select city, avg(age) as avg_age group by city having avg_age > 30
select city, count(*) as cnt, avg(age) as avg_age group by city having cnt > 1 and avg_age > 25
```

## Expressions
jonq supports basic arithmetic expressions:
```bash
select name, age + 10 as age_plus_10
select name, max(orders.price) - min(orders.price) as price_range
```

## Complex Query Examples

### Filtering with Multiple Conditions
```bash
select name, age if age > 25 and (city = 'New York' or city = 'Chicago')
```

### Nested Fields with Group By
```bash
select profile.address.city, count(*) as user_count, avg(profile.age) as avg_age group by profile.address.city
```

### Aggregation with Filtering
```bash
select sum(orders.price) as total_sales if orders.price > 100
```

### Combining Multiple Features
```bash
select name, profile.age, count(orders) as order_count if profile.age > 25 group by profile.address.city sort order_count desc 5
```

### Quoted String Values
When using string values in conditions, use single or double quotes:
```bash
select name, city if city = 'New York'
select name, city if city = "Los Angeles"
```

### Special Character Handling
Field names with special characters require quotes:
```bash
select "user-id", 'total$cost'
select name if "user-id" > 100
```

### Null Handling
jonq automatically handles null values in JSON input:
```bash
select name, age if age is not null
```
