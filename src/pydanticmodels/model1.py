from pydantic import BaseModel

# Basics: BaseModel + constructor
# BaseModel turns a class into a validated data container.
# Fields with type hints define what data is allowed.

class User(BaseModel):
    name: str
    age: int


# Constructor — use when you already know the field values in code.
# Validates types and raises ValidationError on bad input.
user = User(name="John", age=30)
print(user)          # User(name='John', age=30)
print(user.name)     # access fields like normal attributes
print(user.age)

# Serialization — convert validated model back to Python dict / JSON string.
print(user.model_dump())       # {'name': 'John', 'age': 30}
print(user.model_dump_json())  # '{"name":"John","age":30}'


# Nested models
# A field can be another BaseModel. Pydantic auto-validates nested dicts.

class Address(BaseModel):
    city: str

class Person(BaseModel):
    name: str
    age: int
    address: Address


# Nested dict is accepted — Pydantic converts it into an Address instance.
person = Person(
    name="Indra",
    age=25,
    address={"city": "Bangalore"}
)
print(person.__dict__)   # raw internal dict (includes nested Address object)
print(person.model_dump())  # clean dict: {'name': '...', 'age': 25, 'address': {'city': '...'}}


# model_validate vs constructor
# User(name="John", age=30)     → constructor (keyword args)
# User(**data)                   → same as constructor, unpack a dict
# User.model_validate(data)      → validate external data (API, JSON, DB row)
#
# Both validate, but model_validate also supports:
#   strict, from_attributes, context, by_alias

data1 = {
    "name": "Indra",
    "age": 27
}

user1 = User.model_validate(data1)
print(user1)            # User(name='Indra', age=27)
print(type(user1))      # <class '__main__.User'> — returns a User instance, not a dict


# Type coercion — Pydantic converts compatible types automatically.
# "27" (str) → 27 (int). Works with model_validate and constructor.
data2 = {
    "name": "Indra",
    "age": "27"
}

user2 = User.model_validate(data2)
print(user2)            # User(name='Indra', age=27) — age is int, not str


# model_validate_json — validate a JSON string directly (common for HTTP request bodies).
# Pair of model_dump_json (output) ↔ model_validate_json (input).
json_data = '{"name": "Indra", "age": 27}'
user_json = User.model_validate_json(json_data)
print(user_json)        # User(name='Indra', age=27)

# invalid_json = '{"name": "Indra", "age": "not-a-number"}'
# User.model_validate_json(invalid_json)  # ValidationError


# Optional fields + model_dump options
# age: int | None  → field can be an int or None (optional/nullable).

class UserNew(BaseModel):
    name: str
    age: int | None
    password: str

user3 = UserNew(name="John", age=None, password="secret123")

# exclude_none=True  → drop fields whose value is None from output
print(user3.model_dump(exclude_none=True))
# {'name': 'John', 'password': 'secret123'}

# exclude={"password"}  → omit specific fields (useful for API responses)
print(user3.model_dump(exclude={"password"}))
# {'name': 'John', 'age': None}

# include={"name", "age"}  → only include listed fields (whitelist)
print(user3.model_dump(include={"name", "age"}))
# {'name': 'John', 'age': None}



# Validation vs serialization pipeline

# input (dict/kwargs)  →  Pydantic validation  →  typed model instance
# typed model instance →  Pydantic serialization →  dict / JSON
