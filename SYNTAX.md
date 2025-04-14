## Basic Syntax

The general form of a jonq query is:
```bash
select <fields> [if <condition>] [group by <fields>] [sort <field> [asc|desc] [limit]]
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
select name, active if active = 
```
### Supported Operators

`=`, `==`: Equal to
`!=`: Not equal to
`>`: Greater than
`<`: Less than
`>=`: Greater than or equal to
`<=`: Less than or equal to

### Logical Operators

`and`: Logical AND
`or`: Logical OR

### Complex Conditions
```bash
select name, age if age > 25 and city = 'New York'
select name, age if age > 30 or city = 'Los Angeles'
select name, age if (age > 30 and city = 'Chicago') or (age < 25 and city = 'New York')
```

### Nested Field Conditions
```bash
select name if profile.age > 30
select name if orders[0].price > 100
select name if profile.address.city = 'New York'
```

### Sorting and Limiting

#### Sorting
Use `sort` followed by a field name to sort results:
```bash
select name, age sort age
```

#### Sort Direction
Specify `asc` (default) or `desc` for ascending or descending order:
```bash
select name, age sort age asc
select name, age sort age desc
```

#### Limiting Results
Add a number after the sort direction to limit the number of results:
```bash
select name, age sort age desc 5
```

This returns the top 5 results sorted by age in descending order.

### Aggregation Functions
jonq supports the following aggregation functions:

#### count
Count the number of items:

```bash
select count(*) as user_count
select count(orders) as orders_count
```

#### sum
Calculate the sum of numeric values:
```bash
select sum(age) as total_age
select sum(orders.price) as total_sales
```

#### avg
Calculate the average of numeric values:
```bash
select avg(age) as average_age
select avg(orders.price) as average_price
```

#### max
Find the maximum value:
```bash
select max(age) as oldest
select max(orders.price) as highest_price
```

#### min
Find the minimum value:
```bash
select min(age) as youngest
select min(orders.price) as lowest_price
```

### Grouping with GROUP BY
Group data and perform aggregations per group:
```bash
select city, count(*) as user_count group by city
select city, avg(age) as avg_age group by city
select profile.address.city, count(*) as user_count group by profile.address.city
```

### Expressions
jonq supports basic arithmetic expressions:
```bash
select name, age + 10 as age_plus_10
select name, max(orders.price) - min(orders.price) as price_range
```

### Complex Query Examples

#### Filtering with Multiple Conditions
```bash
select name, age if age > 25 and (city = 'New York' or city = 'Chicago')
```

#### Nested Fields with Group By
```bash
select profile.address.city, count(*) as user_count, avg(profile.age) as avg_age group by profile.address.city
```

#### Aggregation with Filtering
```bash
select sum(orders.price) as total_sales if orders.price > 100
```

#### Combining Multiple Features
```bash
select name, profile.age, count(orders) as order_count if profile.age > 25 group by profile.address.city sort order_count desc 5
```

#### Quoted String Values
When using string values in conditions, use single or double quotes:
```bash
select name, city if city = 'New York'
select name, city if city = "Los Angeles"
```

#### Special Character Handling
Field names with special characters require quotes:
```bash
select "user-id", 'total$cost'
select name if "user-id" > 100
```

When both the field name and value contain quotes, use different quote types:

```bash
select name if "user's name" = 'John Doe'
```

#### Null Handling
jonq automatically handles null values in JSON input:
```bash
select name, age if age is not null
```