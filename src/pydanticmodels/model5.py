from typing import Literal
from pydantic import BaseModel, EmailStr, HttpUrl, PositiveInt, Field


# Common Pydantic types — built-in validated types, better than hand-rolled checks.
# EmailStr, HttpUrl, PositiveInt, etc. are Annotated types with validation baked in.
# EmailStr requires: pip install email-validator  (or pydantic[email])

class Contact(BaseModel):
    email: EmailStr
    website: HttpUrl
    score: PositiveInt


contact = Contact(
    email="ip@gmail.com",
    website="https://example.com",
    score=10,
)
print(contact)

# Contact(email="not-an-email", website="https://example.com", score=10)  # ValidationError
# Contact(email="ip@gmail.com", website="not-a-url", score=10)            # ValidationError
# Contact(email="ip@gmail.com", website="https://example.com", score=-1)  # ValidationError


# Literal — field must be one of the listed exact values (great for enums/status fields).

class Order(BaseModel):
    status: Literal["pending", "shipped", "delivered"]
    priority: Literal["low", "medium", "high"] = "medium"


order = Order(status="pending")
print(order)

# Order(status="cancelled")  # ValidationError — not in allowed values


# Union (|) — field can be one of several types. Pydantic tries to match the correct type.

class Payment(BaseModel):
    amount: float
    reference: str | int   # accepts "ABC123" or 12345


pay1 = Payment(amount=99.0, reference="ABC123")
pay2 = Payment(amount=49.0, reference=12345)
print(pay1, pay2)


# Union of models — different shapes of input for the same field.

class CreditCard(BaseModel):
    type: Literal["card"] = "card"
    card_number: str

class UPI(BaseModel):
    type: Literal["upi"] = "upi"
    upi_id: str


class Checkout(BaseModel):
    method: CreditCard | UPI


checkout1 = Checkout(method={"type": "card", "card_number": "4111111111111111"})
checkout2 = Checkout(method={"type": "upi", "upi_id": "user@upi"})
print(checkout1.method)
print(checkout2.method)


# Collections — list[...] and dict[...] fields. Pydantic validates each item/key/value.

class Tag(BaseModel):
    name: str


class Article(BaseModel):
    title: str
    tags: list[str]                          # list of strings
    tag_objects: list[Tag]                   # list of nested models
    metadata: dict[str, str]                 # string keys and string values
    ratings: dict[str, PositiveInt] = Field(default_factory=dict)


# tuple input is coerced to list when field type is list[...]
article = Article(
    title="Learning Pydantic",
    tags=("python", "pydantic"),             # tuple → list[str]
    tag_objects=[{"name": "backend"}, {"name": "validation"}],
    metadata={"author": "Indra", "level": "beginner"},
    ratings={"quality": 5, "clarity": 4},
)
print(article.tags)                         # ['python', 'pydantic']
print(article.tag_objects[0].name)          # backend
print(article.model_dump())

# Article(title="X", tags="not-a-list", metadata={})  # ValidationError
