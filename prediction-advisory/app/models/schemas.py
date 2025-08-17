from pydantic import BaseModel, Field, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema
import datetime
from typing import List, Optional, Dict, Any
from bson import ObjectId


class PyObjectId(ObjectId):
    """Pydantic v2-compatible ObjectId type for MongoDB."""

    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type, _handler):
        # Defines how the type is validated and serialized
        return core_schema.no_info_after_validator_function(
            cls.validate,
            core_schema.str_schema()
        )

    @classmethod
    def validate(cls, v: Any) -> ObjectId:
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(
        cls, _core_schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        # Modify JSON schema so OpenAPI sees it as a string
        json_schema = handler(_core_schema)
        json_schema.update(type="string")
        return json_schema


class FinancialRecord(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    date: datetime.date
    type: str  # "inflow" or "outflow"
    amount: float
    description: str
    category: str
    vendor_id: Optional[str] = None
    client_id: Optional[str] = None
    due_date: Optional[datetime.date] = None
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

    class Config:
        populate_by_name = True


class Alert(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    alert_id: str
    anchor_date: datetime.date
    breach_date: datetime.date
    days_to_breach: int
    projected_balance: float
    threshold: float
    severity: str
    actions: List[Dict[str, Any]]
    raw_message: Dict[str, Any]
    polished_message: Optional[str] = None
    sent: bool = False
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

    class Config:
        populate_by_name = True


class ActionTask(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    alert_id: str
    action_type: str
    description: str
    amount: Optional[float] = None
    target_id: Optional[str] = None
    delay_days: Optional[int] = None
    status: str = "pending"
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

    class Config:
        populate_by_name = True


class Forecast(BaseModel):
    date: datetime.date
    predicted_balance: float
    lower_bound: float
    upper_bound: float
    confidence: float


class SimulationRequest(BaseModel):
    alert_id: str
    action_index: int


class SimulationResponse(BaseModel):
    success: bool
    message: str
    updated_forecast: List[Forecast]
    new_breach_date: Optional[datetime.date] = None
